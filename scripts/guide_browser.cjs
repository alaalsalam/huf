/* Explicit site; generated credentials live only in Node memory and child stdin. */
const fs = require('fs'), path = require('path'), cp = require('child_process'), crypto = require('crypto');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const SITE = process.env.GUIDE_TEST_SITE, BENCH = process.env.GUIDE_TEST_BENCH, OUT = process.env.GUIDE_TEST_OUTPUT;
if (!SITE || !BENCH || !OUT) throw Error('Explicit GUIDE_TEST_SITE, GUIDE_TEST_BENCH, GUIDE_TEST_OUTPUT required');
const origin = new URL(SITE).origin;
const token = crypto.randomBytes(6).toString('hex');
const users = ['allowed', 'limited'].map((persona) => ({persona, email:`huf.guide.${token}.${persona}@example.invalid`, password:crypto.randomBytes(32).toString('base64url'), language:persona==='allowed'?'ar':'en'}));
const result={cases:[],asset_errors:[],external_attempts:[],page_errors:[]};
function fixture(action) {
 const r=cp.spawnSync(path.join(BENCH,'env/bin/python'),[path.join(__dirname,'guide_browser_accounts.py'),'--site',new URL(SITE).hostname],{cwd:path.join(BENCH,'sites'),input:JSON.stringify({token,users,action}),encoding:'utf8'});
 if(r.status!==0)throw Error('Fixture '+action+' failed: '+r.stderr);
 return JSON.parse(r.stdout.trim().split('\n').at(-1));
}
async function api(page, name,args={}) {return page.evaluate(async ({name,args})=>{const r=await fetch('/api/method/'+(name.includes('.')?name:'huf.guide.api.'+name),{method:'POST',headers:{'Content-Type':'application/json','X-Frappe-CSRF-Token':frappe.csrf_token||window.csrf_token},body:JSON.stringify(args)});const d=await r.json();return {status:r.status,message:d.message,exception:d.exception};},{name,args});}
async function check(name, fn) {try{await fn();result.cases.push({name,pass:true});console.log(name+': PASS');}catch(e){result.cases.push({name,pass:false,error:String(e.message).slice(0,600)});console.log(name+': FAIL '+e.message);}}
function assert(ok,msg){if(!ok)throw Error(msg);}
async function main(){let browser,created=false;try{
 result.creation=fixture('create');created=true;
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH,headless:true,args:['--no-sandbox']});
 for(const user of users){
  const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:user.language});
  await ctx.route('**/*',async(route)=>{const url=new URL(route.request().url());if(!['data:','blob:'].includes(url.protocol)&&url.origin!==origin){result.external_attempts.push(url.origin);return route.abort();}return route.continue();});
  const login=await ctx.request.post(origin+'/api/method/login',{form:{usr:user.email,pwd:user.password}});assert(login.status()===200,'Fixture login failed');
  const page=await ctx.newPage();page.on('pageerror',e=>result.page_errors.push((e.stack||e.message).slice(0,900)));page.on('response',r=>{if(r.status()>=400&&r.url().includes('/assets/'))result.asset_errors.push({path:new URL(r.url()).pathname,status:r.status()});});
  await page.goto(origin+'/desk/docs/'+user.language+'/guide/search',{waitUntil:'domcontentloaded'});
  await check(user.persona+' launcher',async()=>{await page.locator('#huf-guide-launcher').waitFor({state:'visible',timeout:30000});assert(await page.locator('#huf-guide-launcher').count()===1,'Duplicate launcher');});
  await check(user.persona+' article ACL',async()=>{
   const r=await api(page,'get_guide',{path:'guide/private-'+token});
   if(user.persona==='allowed')assert(r.status===200&&r.message.title==='Restricted '+token,'Allowed read failed');
   else {assert(r.status===403,'Denied direct read was allowed');assert(!JSON.stringify(r).includes('Restricted '+token)&&!JSON.stringify(r).includes('Confidential sentinel'),'Hidden metadata leaked');}
   const search=await api(page,'search_guides',{query:token});assert(search.status===200,'Search failed');
   assert(search.message.some(i=>i.path==='guide/private-'+token)===(user.persona==='allowed'),'Search ACL mismatch');
   if(user.persona==='limited'){const native=await api(page,'compendium.docs.get_page',{path:'guide/private-'+token});assert(native.status===403&&!JSON.stringify(native).includes('Restricted '+token),'Native source title disclosure');}
  });
  if(user.persona==='allowed'){
   await check('Arabic full journey',async()=>{
    await page.locator('#huf-guide-launcher').click();
    await page.locator('#huf-guide-query').fill('البحث في دليل النظام');await page.locator('#huf-guide-query').press('Enter');
    await page.locator('.huf-guide-card button').filter({hasText:'البحث في دليل النظام'}).first().waitFor({timeout:20000});
    await page.locator('.huf-guide-card button').filter({hasText:'البحث في دليل النظام'}).first().click();
    await page.locator('.huf-guide-article h3').filter({hasText:'البحث في دليل النظام'}).waitFor();
    await page.locator('.huf-guide-source').first().click();
    await page.waitForFunction(()=>frappe.get_route().join('/').includes('docs/ar/guide/search'));
    await page.getByRole('button',{name:'دليل هذه الشاشة',exact:true}).click();
    await page.locator('.huf-guide-card').first().waitFor();
    await page.getByRole('button',{name:'أرشدني خطوة بخطوة',exact:true}).click();
    try { await page.waitForFunction(()=>!!window.huf_system_guide?.tour?.driver?.isActivated); } catch(e) { result.tour_diagnostic=await page.evaluate(()=>({route:frappe.get_route(),items:window.huf_system_guide.items,status:window.huf_system_guide.status.textContent,driver:!!window.huf_system_guide.tour?.driver,nativeTour:typeof frappe.ui.OnboardingTour,scripts:[...document.scripts].map(x=>x.src).filter(x=>x.includes('huf_guide'))})); throw e; }
    assert(await page.locator('.driver-popover-title').count()>0,'Native tour did not render');
    await page.screenshot({path:path.join(OUT,'guide-ar-desktop.png')});
    await page.evaluate(()=>window.huf_system_guide.tour.driver.reset());
   });
   await check('Arabic mobile and keyboard',async()=>{
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>window.huf_system_guide.open());
    assert(await page.locator('#huf-guide-host').getAttribute('dir')==='rtl','Missing RTL');
    assert(await page.locator('#huf-guide-launcher').innerText()==='مرشد النظام','Missing Arabic label');
    const box=await page.locator('#huf-guide-panel').boundingBox();assert(box.width<=390&&box.x>=-1,'Panel overflow');
    await page.screenshot({path:path.join(OUT,'guide-ar-mobile.png')});
    await page.keyboard.press('Escape');assert(await page.locator('#huf-guide-panel').isHidden(),'Escape failed');
   });
   await check('Navigation keeps one panel',async()=>{
    await page.evaluate(()=>{frappe.set_route('docs','en','guide/search');});
    await page.waitForTimeout(700);await page.evaluate(()=>{frappe.set_route('docs','ar','guide/search');});
    await page.waitForTimeout(900);assert(await page.locator('#huf-guide-launcher').count()===1,'Duplicate launcher after navigation');
   });
   await check('Unknown error is explicit',async()=>{
    await page.evaluate(()=>window.huf_system_guide.open());
    await page.getByRole('button',{name:'فسّر خطأ معروفًا',exact:true}).first().click();
    await page.locator('#huf-guide-error').fill('UNREGISTERED_ERROR');await page.locator('#huf-guide-error').press('Enter');
    await page.getByRole('status').filter({hasText:'غير موثّق'}).waitFor();
   });
  } else {
   await check('English panel',async()=>{await page.locator('#huf-guide-launcher').click();assert(await page.locator('#huf-guide-launcher').innerText()==='System Guide','English label');assert(await page.locator('#huf-guide-host').getAttribute('dir')==='ltr','LTR');await page.screenshot({path:path.join(OUT,'guide-en-desktop.png')});});
  }
  await ctx.close();
 }
}finally{if(browser)await browser.close();if(created)result.cleanup=fixture('cleanup');fs.writeFileSync(path.join(OUT,'BROWSER.json'),JSON.stringify(result,null,2)+'\n');}
assert(result.cases.every(r=>r.pass),'Browser acceptance failed');assert(!result.external_attempts.length,'External browser request attempted');assert(!result.asset_errors.length,'Asset errors');}
main().catch(e=>{console.error(e.message);process.exitCode=1;});

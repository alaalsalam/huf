/* Explicit site; generated credentials live only in Node memory and child stdin. */
const fs = require('fs'), path = require('path'), cp = require('child_process'), crypto = require('crypto');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const SITE = process.env.GUIDE_TEST_SITE, BENCH = process.env.GUIDE_TEST_BENCH, OUT = process.env.GUIDE_TEST_OUTPUT;
if (!SITE || !BENCH || !OUT) throw Error('Explicit GUIDE_TEST_SITE, GUIDE_TEST_BENCH, GUIDE_TEST_OUTPUT required');
const origin = new URL(SITE).origin;
const token = crypto.randomBytes(6).toString('hex');
const users = ['allowed', 'limited'].map((persona) => ({persona, email:`huf.guide.${token}.${persona}@example.invalid`, password:crypto.randomBytes(32).toString('base64url'), language:persona==='allowed'?'en':'ar'}));
const ux=process.env.GUIDE_TEST_UX==='1';if(ux)users.push({persona:'admin',email:`huf.guide.${token}.admin@example.invalid`,password:crypto.randomBytes(32).toString('base64url'),language:'ar'});
const result={cases:[],asset_errors:[],external_attempts:[],page_errors:[]};
function fixture(action) {
 const r=cp.spawnSync(path.join(BENCH,'env/bin/python'),[path.join(__dirname,'guide_browser_accounts.py'),'--site',process.env.GUIDE_TEST_SITE_NAME||new URL(SITE).hostname],{cwd:path.join(BENCH,'sites'),input:JSON.stringify({token,users,action,ux,original_checks:result.creation?.original_checks}),encoding:'utf8'});
 if(r.status!==0)throw Error('Fixture '+action+' failed: '+r.stderr);
 return JSON.parse(r.stdout.trim().split('\n').at(-1));
}
async function api(page, name,args={}) {return page.evaluate(async ({name,args})=>{const r=await fetch('/api/method/'+(name.includes('.')?name:'huf.guide.api.'+name),{method:'POST',headers:{'Content-Type':'application/json','X-Frappe-CSRF-Token':frappe.csrf_token||window.csrf_token},body:JSON.stringify(args)});const d=await r.json();return {status:r.status,message:d.message,exception:d.exception,raw:d};},{name,args});}
async function check(name, fn) {if(process.env.GUIDE_TEST_CASES&&!process.env.GUIDE_TEST_CASES.split(',').includes(name))return;try{await fn();result.cases.push({name,pass:true});console.log(name+': PASS');}catch(e){result.cases.push({name,pass:false,error:String(e.message).slice(0,600)});console.log(name+': FAIL '+e.message);}}
function assert(ok,msg){if(!ok)throw Error(msg);}
async function main(){let browser,created=false;try{
 result.creation=fixture('create');created=true;
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH,headless:true,args:['--no-sandbox']});
 for(const user of users){
  const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:user.language});
  await ctx.route('**/*',async(route)=>{const url=new URL(route.request().url());if(!['data:','blob:'].includes(url.protocol)&&url.origin!==origin){result.external_attempts.push(url.origin);return route.abort();}return route.continue();});
  const login=await ctx.request.post(origin+'/api/method/login',{form:{usr:user.email,pwd:user.password}});assert(login.status()===200,'Fixture login failed');
  const page=await ctx.newPage();page.on('pageerror',e=>result.page_errors.push((e.stack||e.message).slice(0,900)));page.on('response',r=>{if(r.status()>=400&&r.url().includes('/assets/'))result.asset_errors.push({path:new URL(r.url()).pathname,status:r.status()});});
  if(user.persona==='admin'){
   await page.goto(origin+'/desk/huf-guide-settings',{waitUntil:'domcontentloaded'});
   await check('Administrator settings and readiness',async()=>{
    await page.waitForFunction(()=>window.cur_frm?.doctype==='HUF Guide Settings'&&!cur_frm.is_dirty());
    await page.getByRole('button',{name:'فحص جاهزية الخدمات',exact:true}).click();
    await page.locator('.guide-readiness-result').waitFor();
    assert((await api(page,'readiness')).status===200,'Manager readiness');
    for(const field of ['allowed_roles','denied_roles','included_screens','excluded_screens','default_language','record_checks_enabled'])assert(await page.locator('[data-fieldname="'+field+'"]').count()>0,'Settings missing '+field);
    await page.locator('.form-layout').screenshot({path:path.join(OUT,'guide-settings-ar.png')});
   });
   await ctx.close();continue;
  }
  await page.goto(origin+'/desk/docs/'+user.language+'/guide/search',{waitUntil:'domcontentloaded'});
  await check(user.persona+' launcher',async()=>{await page.locator('#huf-guide-launcher').waitFor({state:'visible',timeout:30000});assert(await page.locator('#huf-guide-launcher').count()===1,'Duplicate launcher');});
  await check(user.persona+' article ACL',async()=>{
   const r=await api(page,'get_guide',{path:'guide/private-'+token});
   if(user.persona==='allowed'){assert(r.status===200&&r.message.title==='Restricted '+token,'Allowed read failed'); await page.evaluate(p=>{window.huf_system_guide.open();window.huf_system_guide.read(p);},'guide/private-'+token);await page.locator('.huf-guide-article h3').filter({hasText:'Restricted '+token}).waitFor();}
   else {assert(r.status===403,'Denied direct read was allowed');assert(!JSON.stringify(r).includes('Restricted '+token)&&!JSON.stringify(r).includes('Confidential sentinel'),'Hidden metadata leaked');}
   const search=await api(page,'search_guides',{query:token});assert(search.status===200,'Search failed');
   assert(search.message.some(i=>i.path==='guide/private-'+token)===(user.persona==='allowed'),'Search ACL mismatch');
   if(user.persona==='limited'){const native=await api(page,'compendium.docs.get_page',{path:'guide/private-'+token});assert(native.status===403&&!JSON.stringify(native).includes('Restricted '+token),'Native source title disclosure');}
  });
  if(user.persona==='limited'){
   await check('Arabic full journey',async()=>{
    await page.evaluate(()=>window.huf_system_guide.open());
    await page.locator('#huf-guide-query').fill('البحث في دليل النظام');await page.locator('#huf-guide-query').press('Enter');
    await page.locator('.huf-guide-card button').filter({hasText:'البحث في دليل النظام'}).first().waitFor({timeout:20000});
    await page.locator('.huf-guide-card button').filter({hasText:'البحث في دليل النظام'}).first().click();
    await page.locator('.huf-guide-article h3').filter({hasText:'البحث في دليل النظام'}).waitFor();
    await page.locator('.huf-guide-source').first().click();
    await page.waitForFunction(()=>frappe.get_route().join('/').includes('docs/ar/guide/search'));
    await page.getByRole('button',{name:'دليل هذه الشاشة',exact:true}).click();
    await page.locator('.huf-guide-card').first().waitFor();
    await page.getByRole('button',{name:'ابدأ الجولة',exact:true}).click();
    try { await page.waitForFunction(()=>!!window.huf_system_guide?.tour?.driver?.isActivated); } catch(e) { result.tour_diagnostic=await page.evaluate(()=>({route:frappe.get_route(),items:window.huf_system_guide.items,status:window.huf_system_guide.status.textContent,driver:!!window.huf_system_guide.tour?.driver,nativeTour:typeof frappe.ui.OnboardingTour,scripts:[...document.scripts].map(x=>x.src).filter(x=>x.includes('huf_guide'))})); throw e; }
    assert(await page.locator('.driver-popover-title').count()>0,'Native tour did not render');assert((await page.locator('.driver-popover-title').innerText()).includes('مرشد النظام'),'Tour title was not translated');result.journey_user_roles=await page.evaluate(()=>frappe.user_roles);result.api_revision=(await api(page,'bootstrap')).message.api_revision;
    await page.locator('#huf-guide-panel').screenshot({path:path.join(OUT,'guide-ar-desktop.png')});await page.locator('#driver-popover-item').screenshot({path:path.join(OUT,'guide-native-tour.png')});
    await page.evaluate(()=>window.huf_system_guide.tour.driver.reset());
   });
   await check('Arabic mobile and keyboard',async()=>{
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>window.huf_system_guide.open());
    assert(await page.locator('#huf-guide-host').getAttribute('dir')==='rtl','Missing RTL');
    assert(await page.locator('#huf-guide-launcher').innerText()==='مرشد النظام','Missing Arabic label');await page.locator('.huf-guide-card').first().waitFor();
    const box=await page.locator('#huf-guide-panel').boundingBox();assert(box.width<=390&&box.x>=-1,'Panel overflow');
    await page.screenshot({path:path.join(OUT,'guide-ar-mobile.png')});
    await page.keyboard.press('Escape');assert(await page.locator('#huf-guide-panel').isHidden(),'Escape failed');
   });
   await check('Navigation keeps one panel',async()=>{
    await page.evaluate(()=>{frappe.set_route('docs','en','guide/search');});
    await page.waitForTimeout(700);await page.evaluate(()=>{frappe.set_route('docs','ar','guide/search');});
    await page.waitForTimeout(900);assert(await page.locator('#huf-guide-launcher').count()===1,'Duplicate launcher after navigation');
   });
   await check('Late search cannot replace screen guide',async()=>{
    const pattern='**/api/method/huf.guide.api.search_guides';
    await page.route(pattern,async route=>{await new Promise(resolve=>setTimeout(resolve,700));await route.continue();});
    await page.evaluate(token=>{window.huf_system_guide.query.value='البحث';window.huf_system_guide.search();frappe.set_route('docs','en','guide/search');},token);
    await page.waitForTimeout(1700);
    assert(await page.locator('.huf-guide-results .huf-guide-card p').count()===0,'Old search snippet overwrote screen guide');
    await page.unroute(pattern);
   });
   await check('Unknown error is explicit' ,async()=>{
    await page.evaluate(()=>window.huf_system_guide.open());
    await page.locator('#huf-guide-panel summary').click();
    await page.locator('#huf-guide-error').fill('UNREGISTERED_ERROR');await page.locator('#huf-guide-error').press('Enter');
    await page.getByRole('status').filter({hasText:'لا توجد إرشادات موثقة'}).waitFor();
   });
  } else {
   await check('English panel',async()=>{await page.evaluate(()=>window.huf_system_guide.open());assert(await page.locator('#huf-guide-launcher').innerText()==='System Guide','English label');assert(await page.locator('#huf-guide-host').getAttribute('dir')==='ltr','LTR');await page.locator('#huf-guide-panel').screenshot({path:path.join(OUT,'guide-en-desktop.png')});});
  }
  if(ux){
   const screen={screen_type:'Form',screen_name:'Compendium Page'};
   const recordArgs={binding:result.creation.binding,document_name:result.creation.document,context:screen};
   await check(user.persona+' disabled record API',async()=>{assert((await api(page,'check_record',recordArgs)).status===403,'Disabled record check allowed');});
   if(user.persona==='allowed'){
    await page.goto(origin+'/desk/compendium-page/'+encodeURIComponent(result.creation.document),{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.cur_frm?.doctype==='Compendium Page'&&!cur_frm.is_dirty());
    await check('Documented next step and correct field',async()=>{
     await page.evaluate(()=>window.huf_system_guide.open());await page.getByRole('button',{name:'What is the next step?',exact:true}).click();
     await page.getByText('Enter the mandatory title. Synthetic test only.',{exact:true}).waitFor();
     await page.getByRole('button',{name:'Go to field',exact:true}).click();
     await page.waitForFunction(()=>document.activeElement?.closest('[data-fieldname]')?.dataset.fieldname==='title');
    });
    fixture('enable_checks');
    await check('Complete saved request and native form tour',async()=>{
     await page.evaluate(()=>window.huf_system_guide.open());await page.getByRole('button',{name:'What is the next step?',exact:true}).click();
     await page.getByRole('button',{name:'Start tour',exact:true}).click();await page.locator('#driver-popover-item').waitFor();
     await page.evaluate(()=>window.huf_system_guide.tour.driver.reset());
     await page.getByRole('button',{name:'Check this request',exact:true}).click();
     await page.locator('.huf-guide-check[data-state="complete"]').waitFor();
     await page.locator('#huf-guide-panel').screenshot({path:path.join(OUT,'guide-complete.png')});
    });
    await check('Dirty draft is not checked',async()=>{
     await page.evaluate(()=>cur_frm.dirty());
     await page.getByRole('button',{name:'What is the next step?',exact:true}).click();
     let calls=0;const listener=r=>{if(r.url().includes('huf.guide.api.check_record'))calls++;};page.on('request',listener);
     await page.getByRole('button',{name:'Check this request',exact:true}).click();
     await page.getByRole('status').filter({hasText:'Unsaved draft'}).waitFor();assert(calls===0,'Dirty draft was sent');page.off('request',listener);
     await page.evaluate(()=>cur_frm.doc.__unsaved=0);
    });
    fixture('make_incomplete');
    await check('Incomplete saved request is separate from guide',async()=>{
     await page.getByRole('button',{name:'Check this request',exact:true}).click();await page.locator('.huf-guide-check[data-state="incomplete"]').waitFor();
     await page.locator('#huf-guide-panel').screenshot({path:path.join(OUT,'guide-incomplete.png')});
    });
    fixture('make_complete');fixture('unknown_instruction');
    await check('Unknown finding has no guessed action',async()=>{
     const r=await api(page,'check_record',recordArgs);assert(r.status===200&&r.message.state==='unknown'&&!r.message.action,'Unconfirmed instruction presented as a step');
    });
    fixture('withdraw_role');
    await check('Article role withdrawal applies to HTTP',async()=>{const r=await api(page,'get_guide',{path:'guide/private-'+token});assert(r.status===403&&!JSON.stringify(r).includes('Restricted '+token),'Role withdrawal leaked source');});
    fixture('unpublish');
    await check('Unpublished article absent from search',async()=>{const r=await api(page,'search_guides',{query:token});assert(r.status===200&&!r.message.some(v=>v.path==='guide/private-'+token),'Unpublished result leaked');});
   }else{
    await check('Limited saved-record API denied',async()=>{assert((await api(page,'check_record',recordArgs)).status===403,'Limited record access');assert((await api(page,'readiness')).status===403,'Manager diagnostics exposed');});
   }
  }
  await ctx.close();
 }
}finally{if(browser)await browser.close();if(created)result.cleanup=fixture('cleanup');fs.writeFileSync(path.join(OUT,'BROWSER.json'),JSON.stringify(result,null,2)+'\n');}
assert(result.cases.every(r=>r.pass),'Browser acceptance failed');assert(!result.external_attempts.length,'External browser request attempted');assert(!result.asset_errors.length,'Asset errors');}
main().then(()=>process.exit(0)).catch(e=>{console.error(e.message);process.exit(1);});

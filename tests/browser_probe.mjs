import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const output = path.join(root, 'verification', 'approved-brief');
const browserPath = [process.env.BROWSER_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/chromium', '/usr/bin/google-chrome'].find(p => p && existsSync(p));
if (!browserPath) throw new Error('Set BROWSER_PATH to a Chromium browser executable.');
const url = process.env.SITE_URL || 'http://127.0.0.1:4173/';
const profile = await mkdtemp(path.join(os.tmpdir(), 'heather-website-qa-'));
await mkdir(output, {recursive: true});
const browser = spawn(browserPath, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--disable-sync', '--disable-extensions', '--disable-background-networking', 'about:blank'], {stdio:'ignore'});
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const check = (ok, message) => { if (!ok) throw new Error(message); };
const report = {status:'RUNNING', browser: path.basename(browserPath), url, viewports:[], accessibility:[], checks:[]};
let socket;
try {
  let port;
  for (let i=0; i<100; i++) { try { port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]); break; } catch { await wait(100); } }
  check(port, 'Isolated browser did not start.');
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve,reject) => { socket.addEventListener('open',resolve,{once:true}); socket.addEventListener('error',reject,{once:true}); });
  let id=0; const pending=new Map(); const events=[];
  socket.addEventListener('message', e => { const m=JSON.parse(e.data); if (m.id && pending.has(m.id)) {const h=pending.get(m.id);pending.delete(m.id);m.error?h.reject(new Error(m.error.message)):h.resolve(m.result);} else events.push(m); });
  const send=(method,params={}) => new Promise((resolve,reject)=>{const key=++id;const timer=setTimeout(()=>{pending.delete(key);reject(new Error(`CDP timed out: ${method}`));},30000);pending.set(key,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});socket.send(JSON.stringify({id:key,method,params}));});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  const key=async (key,code=key)=>{await send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:({Enter:13,Escape:27,ArrowRight:39,Tab:9})[key]});await send('Input.dispatchKeyEvent',{type:'keyUp',key,code});await wait(80);};
  const shot=async name=>{const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,fromSurface:true});await writeFile(path.join(output,name+'.png'),Buffer.from(r.data,'base64'));};
  async function navigate(width,height=900,hash='') {
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
    const start=events.length;await send('Page.navigate',{url:url+hash});
    for(let i=0;i<100 && !events.slice(start).some(e=>e.method==='Page.loadEventFired');i++)await wait(50);
    await evaluate('document.fonts.ready.then(()=>true)');await wait(1600);
  }
  async function loadImages(){await evaluate(`(async()=>{document.querySelectorAll('img[src]').forEach(i=>i.loading='eager'); await Promise.race([Promise.all([...document.querySelectorAll('img[src]')].map(i=>i.decode().catch(()=>false))),new Promise(r=>setTimeout(r,6000))]);return true;})()`);}
  const geometry=()=>evaluate(`(()=>({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,brokenAnchors:[...document.querySelectorAll('a[href^="#"]')].filter(a=>!document.getElementById(a.hash.slice(1))).map(a=>a.hash),tinyActions:[...document.querySelectorAll('a,button,summary')].filter(e=>e.getClientRects().length && !e.classList.contains('skip-link')).filter(e=>e.getBoundingClientRect().height<44).map(e=>({label:e.textContent.trim(),height:e.getBoundingClientRect().height})),fonts:document.fonts.check('16px Instrument')}))()`);
  async function audit(name){if(!process.env.AXE_PATH)return;await wait(450);await evaluate(await readFile(process.env.AXE_PATH,'utf8'));const r=await evaluate(`axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}).then(r=>({violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),passes:r.passes.length,incomplete:r.incomplete.map(v=>v.id)}))`);report.accessibility.push({name,...r});check(!r.violations.length,`${name}: axe violations ${JSON.stringify(r.violations)}`);}
  await send('Page.enable');await send('Runtime.enable');await send('Log.enable');await send('Network.enable');
  for (const width of [1440,768,390,320]) {
    console.log(`Checking ${width}px`);await navigate(width,width<800?844:900);
    let g=await geometry();check(g.scrollWidth<=g.clientWidth,`Entrance overflow at ${width}`);check(!g.tinyActions.length,`Entrance targets at ${width}`);
    await shot(`entrance-${width}`);if(width===1440)await audit('entrance');
    check(await evaluate("document.querySelector('#main').hidden"),'Entrance must precede the main content.');
    await evaluate("document.querySelector('.enter-button').focus()");await key('Enter');await wait(700);
    check(await evaluate("!document.querySelector('#main').hidden && document.querySelector('#entrance').hidden && document.activeElement.id==='main'"),'Keyboard entry failed.');
    await loadImages();await shot(`home-${width}`);
    g=await geometry();check(g.scrollWidth<=g.clientWidth,`Site overflow at ${width}`);check(!g.brokenAnchors.length,`Broken anchors ${width}`);check(!g.tinyActions.length,`Small targets ${width}: ${JSON.stringify(g.tinyActions)}`);check(g.fonts,'Local fonts failed.');
    const images=await evaluate("[...document.querySelectorAll('img[src]')].every(i=>i.complete&&i.naturalWidth>0)");check(images,`Image failure at ${width}`);
    if(width<=768){await evaluate("document.querySelector('.menu-button').click()");check(await evaluate("document.querySelector('#site-nav').getBoundingClientRect().height>0"),'Menu failed to open.');await key('Escape');check(await evaluate("document.querySelector('.menu-button').getAttribute('aria-expanded')==='false' && document.activeElement.className==='menu-button'"),'Menu escape/focus failed.');}
    else check(await evaluate("document.querySelector('.menu-button').getClientRects().length===0"),'Desktop menu control should be hidden.');
    await evaluate("document.querySelectorAll('.accordion details').forEach(d=>d.open=true)");
    g=await geometry();check(g.scrollWidth<=g.clientWidth,`Expanded content overflow at ${width}`);
    if(width===1440 || width===390){await audit(`full site ${width}`);for(const section of ['philosophy','projects','about','process','services','inquiry']){await evaluate(`document.getElementById('${section}').scrollIntoView({behavior:'instant',block:'start'})`);await wait(350);await shot(`${section}-${width}`);}}
    report.viewports.push({width,height:width<800?844:900,...g,imagesLoaded:images});
  }
  console.log('Checking interaction and privacy paths');await navigate(390,844,'#projects');await loadImages();
  check(await evaluate("document.querySelector('#entrance').hidden"),'Deep links should bypass entrance.');
  await evaluate("document.querySelector('[data-lightbox]').click()");await wait(200);await audit('image viewer');await shot('image-viewer-mobile');
  check(await evaluate("document.querySelector('#study-viewer').open && document.querySelector('#viewer-count').textContent==='1 / 6'"),'Viewer failed to open.');
  await key('ArrowRight');check(await evaluate("document.querySelector('#viewer-count').textContent==='2 / 6'"),'Arrow navigation failed.');
  await key('Escape');check(await evaluate("!document.querySelector('#study-viewer').open && document.activeElement.hasAttribute('data-lightbox')"),'Viewer failed to close and restore focus.');
  await evaluate("document.querySelector('.process-list summary').focus()");await key('Enter');check(await evaluate("document.querySelector('.process-list details').open"),'Keyboard accordion failed.');
  const inquiry=await evaluate(`(()=>{
    const form=document.querySelector('#inquiry-form'), input=s=>document.querySelector(s),state=()=>({error:input('#form-error').textContent,focus:document.activeElement.id||document.activeElement.name});
    form.requestSubmit();const empty=state();input('[name=projectType]').checked=true;input('#name').value='  ';form.requestSubmit();const blankName=state();
    input('#name').value='Preview Reviewer';input('#email').value='invalid';form.requestSubmit();const badEmail=state();
    input('#email').value='review@example.com';input('[name=services]').checked=true;input('#location').value='Dallas';input('#details').value='<img src=x onerror=alert(1)> '+ 'longword'.repeat(80);form.requestSubmit();
    const summary=input('#review-summary').textContent, safe=input('#review-summary').querySelector('img')===null,review=!input('#review-panel').hidden&&document.activeElement.id==='review-panel';
    input('#edit-inquiry').click();const preserved=input('#name').value==='Preview Reviewer';form.requestSubmit();input('#confirm-inquiry').click();
    return {empty,blankName,badEmail,summary,safe,review,preserved,confirmation:!input('#confirmation-panel').hidden&&input('#confirmation-panel').textContent.includes('No message was sent'),storage:localStorage.length+sessionStorage.length,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth};
  })()`);
  check(inquiry.empty.error==='Choose a project type.'&&inquiry.empty.focus==='projectType','Project validation failed.');
  check(inquiry.blankName.error==='Enter your name.'&&inquiry.blankName.focus==='name','Whitespace name validation failed.');
  check(inquiry.badEmail.error==='Enter a valid email address.'&&inquiry.badEmail.focus==='email','Email validation failed.');
  check(inquiry.safe&&inquiry.review&&inquiry.preserved&&inquiry.confirmation&&!inquiry.storage&&!inquiry.overflow,'Inquiry state/privacy failed.');
  await evaluate("document.querySelector('#confirmation-panel').scrollIntoView({behavior:'instant'})");await shot('inquiry-confirmation-mobile');await audit('inquiry confirmation');
  await evaluate("document.querySelector('#start-over').click()");check(await evaluate("!document.querySelector('#form-fields').hidden && document.querySelector('#name').value==='' && !document.querySelector('[name=projectType]:checked')"),'Reset failed.');
  report.inquiry=inquiry;
  await navigate(390,844);await evaluate("document.querySelector('.motion-toggle').click()");
  check(await evaluate("getComputedStyle(document.querySelector('.jasmine-vines')).animationPlayState==='paused'"),'Pause control failed.');
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});await navigate(390,844);
  check(await evaluate("document.getAnimations().length===0 && document.querySelector('.motion-toggle').hidden"),'Reduced motion failed.');
  await evaluate("document.querySelector('.enter-button').click()");check(await evaluate("!document.querySelector('#main').hidden"),'Reduced-motion entry should be immediate.');report.checks.push('Reduced motion and pause controls');
  await send('Emulation.setScriptExecutionDisabled',{value:true});await navigate(320,844);await loadImages();
  const nojs=await evaluate("({mainVisible:!document.querySelector('#main').hidden,formDisabled:document.querySelector('#form-fields').disabled,links:document.querySelectorAll('[data-lightbox][href]').length,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth})");
  check(nojs.mainVisible&&nojs.formDisabled&&nojs.links===6&&!nojs.overflow,'No-JavaScript fallback failed.');report.noJavaScript=nojs;await shot('no-js-mobile');
  await send('Emulation.setScriptExecutionDisabled',{value:false});
  const network=events.filter(e=>e.method==='Network.requestWillBeSent').map(e=>e.params.request);
  check(network.every(r=>r.url.startsWith(url)&&r.method==='GET'),'Unexpected network transmission.');
  const errors=events.filter(e=>e.method==='Runtime.exceptionThrown'||(e.method==='Log.entryAdded'&&e.params.entry.level==='error'));
  check(!errors.length,`Browser errors: ${JSON.stringify(errors)}`);
  report.checks.push('Keyboard entry/menu/accordions/viewer with focus restoration','Six selected gallery images loaded; no overflow at four widths','Inquiry validation/review/edit/confirm/reset; safe text; no storage','No network requests outside local site; no non-GET requests','No JavaScript fallback; no browser errors');
  report.status='PASS';console.log('PASS: responsive layouts, keyboard paths, images, inquiry isolation, motion and fallbacks');
} catch(error) {report.status='FAIL';report.error=String(error);throw error;}
finally {await writeFile(path.join(output,'browser-report.json'),JSON.stringify(report,null,2));socket?.close();browser.kill();await wait(500);await rm(profile,{recursive:true,force:true}).catch(()=>{});}

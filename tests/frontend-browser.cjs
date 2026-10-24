/* Synthetic browser regression. No user profiles, live APIs, credentials, or database.
   Run with installed Playwright available on NODE_PATH; optional WEATHER_TEST_CHROME.
   WEATHER_SCREENSHOT_DIR writes synthetic-only mobile and desktop PNGs. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../web');
const out = process.env.WEATHER_SCREENSHOT_DIR;
const catalog = {
 temperature_c: {label:'Temperature',unit:'°C',kind:'gauge',source_field:'temperature_C'},
 humidity_pct: {label:'Humidity',unit:'%',kind:'gauge',source_field:'humidity'},
 wind_speed_ms: {label:'Wind speed',unit:'m/s',kind:'gauge',source_field:'wind_avg_m_s'},
 wind_gust_ms: {label:'Wind gust',unit:'m/s',kind:'maximum',source_field:'wind_max_m_s'},
 wind_direction_deg: {label:'Wind direction',unit:'°',kind:'circular',source_field:'wind_dir_deg'},
 rain_known_mm: {label:'Known rainfall (partial)',unit:'mm',kind:'accumulation',source_field:'rain_mm'},
 rain_total_mm: {label:'Rain counter',unit:'mm',kind:'cumulative_counter',source_field:'rain_mm'},
 uv_raw: {label:'Raw UV sensor value',unit:'raw',kind:'gauge',source_field:'uv'},
 uv_index: {label:'UV index',unit:'index',kind:'gauge',source_field:'uvi'},
 illuminance_lux: {label:'Illuminance',unit:'lux',kind:'gauge',source_field:'light_lux'},
 pressure_hpa: {label:'Pressure (sensor reported)',unit:'hPa',kind:'gauge',source_field:'pressure_hPa'},
 lightning_distance_km: {label:'Last reported strike distance',unit:'km',kind:'gauge',source_field:'storm_dist_km'},
 lightning_count_raw: {label:'Lightning counter (8 bit)',unit:'count',kind:'raw_counter',source_field:'strike_count'},
 detector_state: {label:'Lightning detector state',unit:null,kind:'status',source_field:'state'},
 battery_level: {label:'Decoder battery level (not charge %)',unit:'fraction level',kind:'gauge',source_field:'battery_ok'},
 battery_ok: {label:'Battery OK',unit:null,kind:'status',source_field:'battery_ok'},
};
const observation = {observed_at:'2026-10-24T04:30:00Z',temperature_c:18.2,humidity_pct:61,wind_speed_ms:3.2,wind_gust_ms:6.2,wind_direction_deg:359,rain_total_mm:18,uv_raw:412,illuminance_lux:23450,lightning_distance_km:null,unavailable_reasons:{lightning_distance_km:'RF no-valid-distance sentinel (63)'},lightning_count_raw:200,detector_state:'listening',battery_ok:false,raw_rf:{model:'Synthetic weather sensor',future_reading:'<img src=x onerror="window.injected=true">',secret_password:'synthetic-do-not-display',extra:{cookie:'synthetic-do-not-display',good:42}},provenance:{transport:'rtl_433',normalizer_version:2}};
const station={id:'test-station',name:'Outdoor array',model:'Synthetic station',stale:false,observation,available_metrics:Object.keys(observation),history:[]};
const dashboard={mode:'demo',sensor_catalog:catalog,locations:[{id:'test-location',name:'Lakehouse',timezone:'America/New_York',stations:[station],forecast:{source:'Synthetic forecast',fetched_at:'2026-10-24T04:30:00Z',status:'ok',daily:[{date:'2026-10-24',weather_code:1,temperature_min_c:10,temperature_max_c:20,precipitation_probability_pct:10}]}}]};
const stat=(first,last,count=2)=>({count,min:typeof first==='number'?Math.min(first,last):null,max:typeof first==='number'?Math.max(first,last):null,mean:typeof first==='number'?(first+last)/2:null,first,last,first_at:'2026-10-24T00:02:00Z',last_at:'2026-10-24T04:00:00Z'});
let rainMode='partial';
function history(metric){
 const kind=catalog[metric].kind; let first=10,last=20;
 if(metric==='wind_gust_ms'){first=3;last=9;}
 if(metric==='wind_direction_deg'){first=359;last=1;}
 if(metric==='lightning_count_raw'){first=190;last=200;}
 if(metric==='rain_total_mm'){first=10;last=18;}
 if(kind==='status'){first=metric==='battery_ok'?true:'idle';last=metric==='battery_ok'?false:'listening';}
 const a=stat(first,first),b=stat(last,last),summary=stat(first,last,4); if(kind.includes('counter')||kind==='status'){a.mean=b.mean=summary.mean=null;}
 if(kind==='circular')summary.mean=0;
 if(kind==='accumulation'){Object.assign(a,{sum:.3,count:2,min:null,max:null,mean:null,unknown_intervals:2,reset_count:1,gap_count:1});Object.assign(b,{sum:.4,count:2,min:null,max:null,mean:null,unknown_intervals:3,reset_count:1,gap_count:2});Object.assign(summary,{sum:.7,count:4,min:null,max:null,mean:null,unknown_intervals:5,reset_count:2,gap_count:3});}
 if(kind==='accumulation'&&rainMode!=='partial'){for(const reading of [a,b,summary]){reading.sum=rainMode==='zero'?0:null;if(rainMode==='baseline')reading.count=0;}}
 return {station_id:station.id,timezone:'America/New_York',start:'2026-10-24T00:02:00Z',end:'2026-10-24T04:30:00Z',actual_start:'2026-10-24T00:02:00Z',actual_end:'2026-10-24T04:00:00Z',bucket_seconds:300,source_resolution_seconds:300,total_observations:4,coverage:{temporal_span_fraction:.88,populated_buckets:2,total_buckets:54},metrics:{[metric]:{...catalog[metric],available:true,count:4}},summary:{observation_count:4,metrics:{[metric]:summary}},points:[{observed_at:'2026-10-24T00:00:00Z',observation_count:2,metrics:{[metric]:a}},{observed_at:'2026-10-24T00:05:00Z',observation_count:0,metrics:{[metric]:{count:0}}},{observed_at:'2026-10-24T04:00:00Z',observation_count:2,metrics:{[metric]:b}}]};
}
let activeBrowser;
(async()=>{
 const browser=activeBrowser=await chromium.launch({headless:true,...(process.env.WEATHER_TEST_CHROME?{executablePath:process.env.WEATHER_TEST_CHROME}:{})});
 const context=await browser.newContext({viewport:{width:390,height:844},locale:'en-US',timezoneId:'Asia/Tokyo'});
 await context.addInitScript(()=>{const OriginalDate=Date;window.Date=class extends OriginalDate{constructor(...args){super(...(args.length?args:['2026-10-24T04:30:00Z']));}static now(){return new OriginalDate('2026-10-24T04:30:00Z').getTime();}};});
 const page=await context.newPage();const errors=[],queries=[];let failDST=false,empty=false;
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('http://weather.test/**',async route=>{
  const url=new URL(route.request().url());assert(url.pathname.startsWith('/weather/'),'all requests stay under prefix');const resource=url.pathname.slice('/weather/'.length);
  if(resource==='api/dashboard'){await route.fulfill({json:dashboard});return;}
  if(resource==='api/history'){
   queries.push(url.searchParams);
   if(failDST){await route.fulfill({status:400,json:{error:'Local time is ambiguous or nonexistent; specify explicit UTC bounds'}});return;}
   const data=history(url.searchParams.get('metric'));if(empty){data.points=[];data.summary.metrics={};data.actual_start=data.actual_end=null;}
   await route.fulfill({json:data});return;
  }
  const asset=resource||'index.html';const types={'.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.html':'text/html','.webmanifest':'application/manifest+json'};
  await route.fulfill({body:fs.readFileSync(path.join(root,asset)),contentType:types[path.extname(asset)]||'text/plain'});
 });
 async function settled(){await page.waitForFunction(()=>document.querySelector('#chart').getAttribute('aria-busy')!=='true'&&document.querySelector('#history-stats').children.length>0);}
 async function metric(key){await Promise.all([page.waitForResponse(r=>r.url().includes('api/history')&&new URL(r.url()).searchParams.get('metric')===key),page.locator('#metric-select').selectOption(key)]);await settled();}
 await page.goto('http://weather.test/weather/');await page.waitForSelector('#content:not([hidden])');await settled();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390);
 assert.equal(await page.locator('#range-select option').count(),14);
 assert.equal(await page.locator('#metric-select option').count(),Object.keys(catalog).length);
 assert((await page.locator('#metric-select option[value="uv_index"]').textContent()).includes('no latest reading'));
 assert(!(await page.locator('#sensor-details dt').allTextContents()).includes('UV index'));
 assert((await page.locator('#sensor-details').textContent()).includes('not solar irradiance'));
 assert((await page.locator('#sensor-details').textContent()).includes('not an hourly or daily strike count'));
 assert((await page.locator('#sensor-details').textContent()).includes('no-valid-distance sentinel'));
 assert(!(await page.locator('#sensor-extras').textContent()).includes('synthetic-do-not-display'));
 await page.locator('#extras-disclosure summary').click();assert.equal(await page.locator('#sensor-extras img').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
 assert.equal((await page.locator('.line').getAttribute('d')).match(/M/g).length,2,'gap must split line');
 assert((await page.locator('.point').first().getAttribute('aria-label')).startsWith('Bucket Oct 23, 2026, 8:02 PM'),'first partial bucket label clips to requested start');assert.equal(await page.locator('#history-resolution').textContent(),'5-minute summaries');
 await page.locator('.point').first().focus();assert((await page.locator('#chart-readout').textContent()).includes('readings'));
 await page.keyboard.press('ArrowRight');assert.equal(await page.locator('.point:focus').getAttribute('data-point'),'1');
 for(const range of ['4h','8h','12h','24h','3d','7d','10d','30d','60d','90d','1y','5y','10y']){
  await Promise.all([page.waitForResponse(r=>r.url().includes('api/history')&&new URL(r.url()).searchParams.get('range')===range),page.locator('#range-select').selectOption(range)]);await settled();assert.equal(queries.at(-1).get('range'),range);
 }
 await metric('wind_gust_ms');assert((await page.locator('#history-current').textContent()).startsWith('20.1'),'gust max9m/s converted to20.1mph');
 await metric('wind_direction_deg');assert.deepEqual(await page.locator('#chart svg text').allTextContents().then(labels=>labels.slice(0,5)),['N','W','S','E','N']);assert.equal((await page.locator('.line').getAttribute('d')).match(/M/g).length,2);
 await metric('lightning_count_raw');assert((await page.locator('#history-current').textContent()).startsWith('200'),'raw count uses last, not sum/mean');
 await metric('rain_known_mm');assert((await page.locator('#history-current').textContent()).includes('0.028 in known'));assert.equal(await page.locator('#chart rect').count(),2);assert.equal(await page.locator('#chart .line').count(),0);assert((await page.locator('#history-stats').textContent()).includes('Unknown intervals5'));assert((await page.locator('#chart-readout').textContent()).includes('not a complete period total'));
 rainMode='baseline';await page.locator('#range-select').selectOption('7d');await settled();assert.equal(await page.locator('#history-current').textContent(),'No measured rain intervals');assert((await page.locator('#history-stats').textContent()).includes('No known intervals'));assert.equal(await page.locator('#chart rect').count(),0);
 rainMode='zero';await page.locator('#range-select').selectOption('3d');await settled();assert.equal(await page.locator('#history-current').textContent(),'0 in known');rainMode='partial';
 await metric('detector_state');assert.equal(await page.locator('.status-history>div').count(),2);assert((await page.locator('.status-history>div').first().textContent()).includes('listening'));
 await metric('battery_ok');assert((await page.locator('#history-current').textContent()).startsWith('No'),'false state is not missing');
 await metric('temperature_c');await page.locator('#range-select').selectOption('custom');await page.locator('#history-start').fill('2026-11-01T01:30');await page.locator('#history-end').fill('2026-11-01T03:30');failDST=true;
 await page.locator('#custom-range button').click();await page.waitForSelector('#history-error:not([hidden])');assert((await page.locator('#history-error').textContent()).includes('because of daylight saving'));assert.equal(queries.at(-1).get('local_start'),'2026-11-01T01:30');assert.equal(queries.at(-1).get('timezone'),'America/New_York');
 failDST=false;await page.locator('#history-start').fill('2026-11-01T02:30');await page.locator('#custom-range button').click();await settled();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390,'custom controls do not overflow');
 await page.locator('#celsius').click();assert((await page.locator('#history-current').textContent()).includes('°C'));
 if(out){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'sensor-history-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});await page.waitForTimeout(150);await page.screenshot({path:path.join(out,'sensor-history-desktop.png'),fullPage:true});}
 station.observation={observed_at:'2026-10-24T04:30:00Z',temperature_c:null,detector_state:'listening',battery_ok:null,battery_level:.5};
 await page.reload();await page.waitForSelector('#content:not([hidden])');await settled();assert.equal(await page.locator('#temperature').textContent(),'listening');assert((await page.locator('#hero-detail').textContent()).includes('Live sensor data'));assert.equal(await page.locator('#condition-label').textContent(),'Lightning detector state');assert.equal(await page.locator('#battery').textContent(),'Decoder battery level 0.5');
 empty=true;await page.locator('#range-select').selectOption('10y');await page.waitForFunction(()=>document.querySelector('#history-current').textContent==='No readings in this range');
 assert.equal(errors.length,0,errors.join(';'));assert(queries.every(q=>q.get('max_points')==='600'));
 console.log(JSON.stringify({passed:true,checks:42,presetRequests:13,mobileWidth:390,queryCount:queries.length,screenshots:out||null}));await browser.close();
})().catch(async error=>{console.error(error);if(activeBrowser)await activeBrowser.close();process.exitCode=1;});

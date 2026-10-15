import assert from 'node:assert/strict';
import process from 'node:process';
import path from 'node:path';
import { chromium, expect } from 'file:///C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi/frontend/node_modules/@playwright/test/index.mjs';

const root = process.env.UI_REVIEW_RUN_PATH ?? 'D:/dianzi/reports/runs/recovery_r04_live_ui_review_1_20261015';
const base = 'http://127.0.0.1:25300';
const dimensionLabels = {cvss:'CVSS 评分',epss:'EPSS 可能性',kev:'KEV 目录',cwe:'CWE 弱点',atlas:'ATLAS 映射',versions:'影响版本',literature:'论文关联',poc:'PoC 核查',exposure:'暴露统计'};
const statuses = {available:'已取得',not_found:'未发现',not_applicable:'不适用',conflict:'有冲突',blocked:'受阻',failed:'失败',pending:'待处理'};
const freshness = {current:'当前',stale:'已过期',unknown:'时效未知'};
const evidence = {started_at:new Date().toISOString(),cases:[],viewports:[],network:[],external:[],limitations:[]};
const check = async (name, callback) => {try {const result=await callback();evidence.cases.push({name,status:'passed',result:result??null});return result;}catch(error){evidence.cases.push({name,status:'failed',error:String(error)});throw error;}};
const browser = await chromium.launch({headless:true});
try {
  for (const width of [1366,390]) {
    const context=await browser.newContext({viewport:{width,height:width===390?844:900},reducedMotion:'no-preference'});
    const page=await context.newPage();
    page.setDefaultTimeout(12000);
    const observation={width,api:[],page_errors:[],request_failures:[]};
    evidence.viewports.push(observation);
    page.on('pageerror',error=>observation.page_errors.push(String(error)));
    page.on('requestfailed',request=>observation.request_failures.push({path:new URL(request.url()).pathname,failure:request.failure()?.errorText}));
    page.on('response',response=>{const url=new URL(response.url());if(url.pathname.startsWith('/v1/')){evidence.network.push({width,path:url.pathname,status:response.status(),from_service_worker:response.fromServiceWorker()});}});
    await check(`${width} anonymous entry and real navigation`,async()=>{
      await page.goto(base+'/#events');
      await expect(page.getByRole('link',{name:'登录并核对权限',exact:true})).toBeVisible();
      await expect(page.locator('.event-record-link')).toHaveCount(0);
      await page.getByRole('link',{name:'登录并核对权限',exact:true}).click();
      await expect(page.getByLabel('用户名',{exact:true})).toBeVisible();
    });
    await check(`${width} real session login`,async()=>{
      await page.getByLabel('用户名',{exact:true}).fill(process.env.DIANZI_E2E_USERNAME);
      await page.getByLabel('密码',{exact:true}).fill(process.env.DIANZI_E2E_PASSWORD);
      const loginPromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/auth/login'&&response.request().method()==='POST');
      await page.getByRole('button',{name:'登录工作台',exact:true}).click();
      const response=await loginPromise;assert.equal(response.status(),200);
      await expect(page.getByRole('button',{name:'退出登录',exact:true})).toBeVisible();
      await expect(page.locator('.mode-label')).toContainText('真实 / Live');
      observation.api.push({kind:'login',status:response.status()});
    });
    let list, detail, selected, quote;
    await check(`${width} actual list and source counts`,async()=>{
      const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/events'&&response.status()===200);
      await page.getByRole('link',{name:'情报列表',exact:true}).click();
      const response=await responsePromise;list=await response.json();assert.equal(list.data_mode,'live');assert.equal(list.schema_version,2);assert.ok(list.items.length>0);
      await expect(page.locator('.event-record-link')).toHaveCount(list.items.length);
      const rows=page.getByRole('table',{name:'情报事件列表',exact:true}).locator('tbody tr');
      for(let index=0;index<list.items.length;index++){const item=list.items[index];await expect(rows.nth(index).locator('.event-record-link')).toHaveText(item.title);await expect(rows.nth(index).locator('.data-value')).toHaveText(String(item.source_count));await expect(rows.nth(index).locator('.freshness-label')).toHaveText(freshness[item.freshness]);}
      await expect(page.locator('.list-pagination')).toContainText(`本页 ${list.items.length} 条 · 真实 / Live`);
      await expect(page.locator('.query-toolbar')).toContainText('本页数量不代表全部事件总数');
      observation.list={status:response.status(),data_mode:list.data_mode,count:list.items.length,next_cursor_present:list.next_cursor!==null,items:list.items};
      await page.screenshot({path:path.join(root,`list-${width}.png`),fullPage:true});
      return {status:response.status(),count:list.items.length};
    });
    await check(`${width} real event nine dimensions and provenance`,async()=>{
      selected=list.items[0];
      const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname===`/v1/events/${selected.event_id}`&&response.status()===200);
      await page.locator('.event-record-link').first().click();
      const response=await responsePromise;detail=await response.json();assert.equal(detail.data_mode,'live');assert.equal(detail.event.event_id,selected.event_id);
      await expect(page.locator('.dimension-row')).toHaveCount(9);
      for(const [name,label] of Object.entries(dimensionLabels)){const row=page.locator('.dimension-row').filter({has:page.locator('.dimension-name',{hasText:label})});const values=detail.dimensions.filter(item=>item.dimension===name);if(values.length===0)await expect(row).toContainText('未提供该维度');else for(const value of values){await expect(row).toContainText(statuses[value.status]);await expect(row).toContainText(freshness[value.freshness]);if(value.error_code)await expect(row).toContainText(value.error_code);}}
      for(const claim of detail.claims){const entry=page.locator('.claim-row').filter({has:page.locator('p',{hasText:claim.display_value})});assert.ok(await entry.count()>0);}
      const distinctSources=new Set(detail.revisions.map(revision=>revision.source_id));assert.equal(detail.event.source_count,distinctSources.size);
      observation.detail=detail;
      await page.screenshot({path:path.join(root,`detail-${width}.png`),fullPage:true});
      return {event_id:selected.event_id,dimensions:detail.dimensions.map(item=>({dimension:item.dimension,status:item.status,freshness:item.freshness})),missing:Object.keys(dimensionLabels).filter(name=>!detail.dimensions.some(item=>item.dimension===name))};
    });
    await check(`${width} keyboard opens exact revision evidence`,async()=>{
      const citation=page.getByRole('link',{name:'原文片段 [1]',exact:true}).first();
      const href=await citation.getAttribute('href');const parts=href.split('/');const span=parts[3];const revision=parts[5]??null;
      const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname===`/v1/evidence/${span}`&&response.status()===200);
      await citation.focus();await citation.press('Enter');
      const response=await responsePromise;quote=await response.json();assert.equal(quote.span_id,span);if(revision!==null)assert.equal(quote.revision_id,revision);assert.equal(quote.data_mode,'live');
      await expect(page.locator('.evidence-body blockquote')).toHaveText(quote.quote_text);await expect(page.getByRole('complementary',{name:'证据检视',exact:true})).toBeFocused();
      await expect(page.locator('.evidence-body')).toContainText('引文存在 ≠ 内容支持');await expect(page.locator('.evidence-body')).toContainText(`[${quote.start_offset}, ${quote.end_offset})`);await expect(page.locator('.evidence-body')).toContainText(quote.revision_id);if(quote.json_pointer)await expect(page.locator('.evidence-body')).toContainText(quote.json_pointer);
      for(const [field,label] of Object.entries({source_published_at:'源发布时间',source_modified_at:'源修订时间',first_observed_at:'首次观察',ingested_at:'入库完成'})){const dd=page.locator('.evidence-body dt').filter({hasText:label}).locator('xpath=following-sibling::dd[1]');await expect(dd).toHaveText(quote[field]??'未知 / 未留存');}
      const link=page.getByRole('link',{name:'打开来源地址 ↗',exact:true});await expect(link).toHaveAttribute('href',quote.source_uri);await expect(link).toHaveAttribute('rel','noopener noreferrer');assert.ok(/^https:\/\/(nvd\.nist\.gov|github\.com)\//.test(quote.source_uri));
      observation.evidence=quote;
      await page.screenshot({path:path.join(root,`evidence-${width}.png`),fullPage:true});
      return {status:response.status(),span_id:quote.span_id,revision_id:quote.revision_id,source_uri:quote.source_uri,locator_kind:quote.locator_kind};
    });
    await check(`${width} actual reload fetch persists evidence`,async()=>{
      const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname===`/v1/evidence/${quote.span_id}`&&response.status()===200);
      await page.reload();const response=await responsePromise;const reloaded=await response.json();assert.equal(reloaded.quote_sha256,quote.quote_sha256);assert.equal(reloaded.revision_id,quote.revision_id);await expect(page.locator('.evidence-body blockquote')).toHaveText(quote.quote_text);
      return {new_http_request:true,status:response.status(),quote_sha256:reloaded.quote_sha256};
    });
    await check(`${width} motion click boundary and reduced motion`,async()=>{
      const motion=page.getByTestId('ambient-motion');const first=await motion.evaluate(element=>getComputedStyle(element).transform);await page.waitForTimeout(1100);const second=await motion.evaluate(element=>getComputedStyle(element).transform);assert.notEqual(first,second);await expect(page.getByTestId('ambient-backdrop')).toHaveCSS('pointer-events','none');
      const css=await motion.evaluate(element=>{const style=getComputedStyle(element);return {name:style.animationName,duration:style.animationDuration,opacity:style.opacity};});assert.equal(css.name,'topology-drift');assert.equal(css.duration,'22s');
      await page.emulateMedia({reducedMotion:'reduce'});await expect(motion).toHaveCSS('animation-name','none');const reducedFirst=await motion.evaluate(element=>getComputedStyle(element).transform);await page.waitForTimeout(300);const reducedSecond=await motion.evaluate(element=>getComputedStyle(element).transform);assert.equal(reducedFirst,reducedSecond);
      observation.motion={first,second,...css,reducedFirst,reducedSecond};await page.emulateMedia({reducedMotion:'no-preference'});
      return observation.motion;
    });
    await check(`${width} layout keyboard and readable evidence`,async()=>{
      const layout=await page.evaluate(()=>({width:innerWidth,document_width:document.documentElement.scrollWidth,body_width:document.body.scrollWidth,quote_font:getComputedStyle(document.querySelector('.evidence-body blockquote')).fontSize,quote_bounds:document.querySelector('.evidence-body blockquote').getBoundingClientRect().toJSON(),scroll_y:scrollY}));assert.ok(layout.document_width<=width);assert.ok(layout.body_width<=width);assert.ok(parseFloat(layout.quote_font)>=14);
      const skip=page.getByRole('link',{name:'跳到主要内容',exact:true});await skip.focus();await skip.press('Enter');await expect(page.locator('main')).toBeFocused();assert.ok(page.url().includes('#events/'));
      const outline=await page.locator('main').evaluate(element=>({style:getComputedStyle(element).outlineStyle,width:getComputedStyle(element).outlineWidth}));assert.equal(outline.style,'solid');assert.equal(outline.width,'2px');
      observation.layout=layout;return {layout,outline};
    });
    if(width===1366){
      await check('actual original source opens independently of href',async()=>{
        const link=page.getByRole('link',{name:'打开来源地址 ↗',exact:true});const popupPromise=page.waitForEvent('popup');await link.click();const popup=await popupPromise;let response=null;let failure=null;try{response=await popup.goto(quote.source_uri,{waitUntil:'domcontentloaded',timeout:12000});}catch(error){failure=String(error);}const outcome={expected_uri:quote.source_uri,actual_url:popup.url(),http_status:response?.status()??null,title:await popup.title(),loaded:failure===null,failure};evidence.external.push(outcome);await popup.close();return outcome;
      });
    }
    await check(`${width} real search empty remains uncertain`,async()=>{
      await page.getByLabel('检索关键词',{exact:true}).fill('ui-review-no-match-7184-20261015');const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/events'&&new URL(response.url()).searchParams.get('q')==='ui-review-no-match-7184-20261015');await page.getByRole('button',{name:'检索情报',exact:true}).click();const response=await responsePromise;const result=await response.json();assert.equal(response.status(),200);assert.equal(result.items.length,0);assert.equal(result.data_mode,'live');await expect(page.getByRole('heading',{name:'本次查询没有事件记录',exact:true})).toBeVisible();await expect(page.getByText('服务已完成此次查询并返回空结果。这不代表没有相关风险；可以调整筛选或查看来源范围。',{exact:true})).toBeVisible();await expect(page.locator('.event-detail')).toHaveCount(0);await expect(page.locator('.evidence-body')).toHaveCount(0);await page.screenshot({path:path.join(root,`empty-${width}.png`),fullPage:true});return {status:response.status(),count:result.items.length};
    });
    await check(`${width} actual product filter`,async()=>{
      await page.getByLabel('检索关键词',{exact:true}).fill('');await page.getByLabel('产品筛选',{exact:true}).fill('vllm');const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/events'&&new URL(response.url()).searchParams.get('product')==='vllm');await page.getByRole('button',{name:'检索情报',exact:true}).click();const response=await responsePromise;const result=await response.json();assert.equal(response.status(),200);assert.ok(result.items.length>0);await expect(page.locator('.event-record-link')).toHaveCount(result.items.length);return {status:response.status(),count:result.items.length,filter:'saved affected_product claims'};
    });
    await check(`${width} malformed actual time filter remains error`,async()=>{
      await page.getByLabel('产品筛选',{exact:true}).fill('');await page.getByLabel('修订时间之后',{exact:true}).fill('invalid-time-ui-review');const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/events'&&new URL(response.url()).searchParams.get('updated_after')==='invalid-time-ui-review');await page.getByRole('button',{name:'检索情报',exact:true}).click();const response=await responsePromise;const result=await response.json();assert.equal(response.status(),422);assert.equal(result.error.code,'validation_error');await expect(page.getByRole('heading',{name:'查询未完成',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'本次查询没有事件记录',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'重新查询',exact:true})).toBeVisible();await expect(page.locator('.event-record-link')).toHaveCount(0);await page.screenshot({path:path.join(root,`invalid-filter-${width}.png`),fullPage:true});return {status:response.status(),code:result.error.code};
    });
    await check(`${width} pagination to actual NVD evidence`,async()=>{
      await page.getByLabel('修订时间之后',{exact:true}).fill('');let responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/events'&&response.status()===200);await page.getByRole('button',{name:'检索情报',exact:true}).click();let response=await responsePromise;let batch=await response.json();const pageIds=[];let nvd=null;
      for(let index=0;index<4;index++){pageIds.push(batch.items.map(item=>item.event_id));nvd=batch.items.find(item=>item.external_ids.some(id=>id.startsWith('CVE-'))&&item.title.startsWith('CVE-'));if(nvd||batch.next_cursor===null)break;responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/events'&&new URL(response.url()).searchParams.has('cursor'));await page.getByRole('button',{name:'下一页',exact:true}).click();response=await responsePromise;assert.equal(response.status(),200);batch=await response.json();await expect(page.locator('.event-record-link')).toHaveCount(batch.items.length);}
      assert.ok(nvd,'bounded four actual pages must contain NVD event');const flattened=pageIds.flat();assert.equal(new Set(flattened).size,flattened.length);responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname===`/v1/events/${nvd.event_id}`);await page.locator(`.event-record-link[href="#events/${nvd.event_id}"]`).click();response=await responsePromise;const nvdDetail=await response.json();await expect(page.locator('.dimension-row')).toHaveCount(9);const citation=page.getByRole('link',{name:'原文片段 [1]',exact:true}).first();const span=(await citation.getAttribute('href')).split('/')[3];responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname===`/v1/evidence/${span}`);await citation.click();response=await responsePromise;const nvdQuote=await response.json();assert.ok(nvdQuote.source_uri.startsWith('https://nvd.nist.gov/'));await expect(page.locator('.evidence-body blockquote')).toHaveText(nvdQuote.quote_text);await expect(page.getByRole('link',{name:'打开来源地址 ↗',exact:true})).toHaveAttribute('href',nvdQuote.source_uri);observation.nvd={detail:nvdDetail,evidence:nvdQuote,pageIds};await page.screenshot({path:path.join(root,`nvd-evidence-${width}.png`),fullPage:true});return {pages:pageIds.length,events_seen:flattened.length,event_id:nvd.event_id,source_uri:nvdQuote.source_uri};
    });
    await check(`${width} sources capability honest`,async()=>{
      await page.getByRole('link',{name:'来源监测',exact:true}).click();await expect(page.getByRole('heading',{name:'本页能力待接通',exact:true})).toBeVisible();await expect(page.getByText('待接通',{exact:true})).toBeVisible();await expect(page.getByRole('table',{name:'来源登记',exact:true}).locator('tbody tr')).toHaveCount(0);return {source_page:'not_connected',source_success_claim:false};
    });
    await check(`${width} real logout clears private frontend state`,async()=>{
      await page.getByRole('link',{name:'会话与权限',exact:true}).click();await page.getByRole('button',{name:'退出登录',exact:true}).click();await expect(page.getByRole('button',{name:'登录工作台',exact:true})).toBeVisible();await page.getByRole('link',{name:'情报列表',exact:true}).click();await expect(page.locator('.event-record-link')).toHaveCount(0);await expect(page.locator('.evidence-body')).toHaveCount(0);await expect(page.locator('.mode-label')).toContainText('登录后确认');return {private_records_visible:false};
    });
    await context.close();
  }
}catch(error){evidence.fatal=String(error);process.exitCode=1;}finally{await browser.close();evidence.ended_at=new Date().toISOString();evidence.counts={passed:evidence.cases.filter(item=>item.status==='passed').length,failed:evidence.cases.filter(item=>item.status==='failed').length,skipped:0};console.log(JSON.stringify(evidence,null,2));}

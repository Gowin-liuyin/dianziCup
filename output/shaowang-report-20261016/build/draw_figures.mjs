import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Presentation, PresentationFile} from '@oai/artifact-tool';

const build=path.dirname(fileURLToPath(import.meta.url));
const root=path.dirname(build);
const specs=JSON.parse(await fs.readFile(path.join(build,'figures.json'),'utf8'));
const P=Presentation.create({slideSize:{width:600,height:420}});
const C={main:'#1F3A5F',eco:'#2E7D8C',agent:'#5B4E8C',store:'#3E6E9E',light:'#F4F7FA',text:'#1A1A1A',muted:'#555555',line:'#4A5568',ok:'#2F7D4F',warn:'#B7791F',bad:'#A33A3A',gray:'#8A94A6'};
let S;
let compactFigure=false;
function textRuns(text,size=14,bold=false){return text.split('\n').map(line=>({runs:(line.match(/[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]+|[^\u3400-\u9fff\u3000-\u303f\uff00-\uffef]+/g)||['']).map(run=>({run,style:{typeface:/[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]/.test(run)?'SimSun':'Times New Roman',fontSize:`${size}px`,bold}}))}));}
function box(t,x,y,w,h,kind='rect',color=C.main,size=14,fill='white',dash='solid'){
  if(compactFigure)size=Math.max(size,kind==='text'?16:18);
  const geom={agent:'roundRect',hub:'hexagon',plugin:'parallelogram',db:'can',external:'roundRect',decision:'diamond',api:'rect',text:'textbox'}[kind]||kind;
  const a=S.shapes.add({geometry:geom,name:t.replaceAll('\n',' ').slice(0,70),position:{left:x,top:y,width:w,height:h},fill:kind==='text'?'white':fill,line:{fill:kind==='text'?'none':color,width:kind==='text'?0:1.2,style:dash}});
  a.text=textRuns(t,size);
  a.text.style={alignment:'center',verticalAlignment:'middle',insets:2,color:C.text,wrap:'word',fontSize:size};
  if(kind==='agent')S.shapes.add({geometry:'rect',position:{left:x+2,top:y+5,width:3,height:h-10},fill:C.agent,line:{fill:'none',width:0}});
  if(kind==='api')S.shapes.add({geometry:'rect',position:{left:x+3,top:y+3,width:w-6,height:h-6},fill:'none',line:{fill:color,width:.65}});
  return a;
}
function label(t,x,y,w,h=24,size=12,color=C.muted){const a=box(t,x,y,w,h,'text',color,size);a.text.color=color;return a;}
function edge(a,b,{kind='straight',color=C.main,dash='solid',from,to,width=2}={}){
 return S.shapes.connect(a,b,{kind,fromSide:from,toSide:to,line:{fill:color,width,style:dash},tail:{type:'triangle',width:'sm',length:'sm'}});
}
function row(items,y,{x=25,w=550,h=52,gap=16,kind='rect',color=C.main,size=14,chain=true}={}){let cw=(w-gap*(items.length-1))/items.length;let r=items.map((t,i)=>box(t,x+i*(cw+gap),y,cw,h,kind,color,size));if(chain)r.slice(1).forEach((b,i)=>edge(r[i],b));return r;}
function note(t,y=375){label(t,20,compactFigure?Math.min(y,370):y,560,compactFigure?45:32,11);}
function group(t,x,y,w,h,color=C.main){const a=box('',x,y,w,h,'rect',color,14,C.light);label(t,x+8,y+5,w-16,22,14,color);return a;}
function slide(id){S=P.slides.add();S.background.fill='white';let q=specs.find(s=>s.id===id);compactFigure=!!q&&q.layout==='半栏';S.speakerNotes.text=q?`${q.id} ${q.title}\n依据：design-dossier.md ${q.source}\n报告位置：${q.location}\n全部图形为原生形状、文本与吸附连接线。设计参数不代表实测。`: '样式母版\n依据：design-dossier.md D22.1\n中文宋体，西文 Times New Roman。';return S;}

slide('STYLE');
label('样式母版',20,12,560,28,18,C.main);
[C.main,C.eco,C.agent,C.store,C.ok,C.warn,C.bad].forEach((c,i)=>{box('',30+i*79,56,56,23,'rect',c,14,c);label(c,22+i*79,82,72,20,11);});
let ss=['agent','hub','plugin','db','api','external','decision'];
let st=['智能体','调度中枢','插件','存储','对外接口','外部来源','判断'];
ss.forEach((k,i)=>box(st[i],25+(i%4)*145,124+Math.floor(i/4)*85,120,52,k,i===0?C.agent:C.main));
row(['主数据流','目标节点'],305,{x:30,w:220,h:38,size:12});
let a=box('失败与重试',320,305,105,38,'rect',C.bad,12);let b=box('死信队列',465,305,105,38,'db',C.bad,12);edge(a,b,{color:C.bad,dash:'dashed',width:1.33});
note('宋体 SimSun  ·  Times New Roman  ·  节点 10.5 pt / 注释 9 pt / 最小 8 pt');

slide('F-01');
const layers=[['接入层','Web / MCP 7 工具 / OpenAPI / CLI / Agent Plugins'],['服务层','intel-core / GraphRAG / 鉴权与结果裁剪'],['智能体编排层','Orchestrator + 8 个角色 / LangGraph'],['知识层','PostgreSQL + pgvector / Neo4j / OpenSearch\nMinIO / Redis Streams 或 NATS JetStream'],['采集层','Connector × N / 自有仓库 webhook'],['数据源层','9 类来源 / 三级可信度 / 分级轮询']];
const lr=layers.map((v,i)=>{let y=14+i*62;box(v[0],16,y,104,48,'rect',C.main,14,C.light);return box(v[1],120,y,350,48,'rect',C.main,13);});
for(let i=5;i>0;i--)edge(lr[i],lr[i-1],{from:'top',to:'bottom'});
['时效可观测','可信与裁决','合规边界','开放生态'].forEach((t,i)=>box(t,488,20+i*92,94,76,'rect',C.eco,13,C.light));
note('PostgreSQL 是事实源；outbox 同步图库与全文索引',386);

slide('F-02');
const mon=box('监测\n9 类来源',42,58,138,62,'external');
const enr=box('富化\n9 个维度',420,58,138,62,'agent',C.agent);
const qa=box('问答\n逐句引用',230,284,140,62,'agent',C.agent);
const core=box('知识图谱\n与事实库',222,154,156,76,'db',C.store);
edge(mon,enr);edge(enr,qa,{kind:'elbow'});edge(qa,mon,{kind:'elbow'});
edge(mon,core);edge(core,enr);edge(core,qa);
label('版本自查',24,235,110);label('MCP 开放',456,235,120);label('Critic 校验',237,100,126);note('时效可观测贯穿发现、富化、校验与服务');

slide('F-03');
row(['采集','归一','富化','校验','存储','服务'],60,{h:58,gap:12,size:14});
const times=['来源发布','首次发现','完成归一','完成富化','可查询'];
const fields=['source_published_at','first_seen_at','normalized_at','enriched_at','queryable_at'];
row(times,190,{h:36,gap:15,size:13});
fields.forEach((t,i)=>label(t,13+i*117,231,112,30,10.67));
box('采集时延',25,282,204,36,'rect',C.main,13,C.light);
box('处理时延',242,282,333,36,'rect',C.main,13,C.light);
box('端到端时延目标值 ≤6 h（待测）',25,338,550,38,'rect',C.warn,14,'white','dashed');
note('统计范围：漏洞类首次发现；日更源单列；DEMO 不计',385);

slide('F-04');
const names=['厂商仓库','Orchestrator','Collector','Triage','Enricher','Critic','GraphWriter','Assessor','编码智能体'];
const lane=names.map((t,i)=>box(t,5+i*66,18,63,34,i===0?'external':i===8?'api':'agent',C.main,10.67));
const ends=names.map((t,i)=>box('',35+i*66,346,1,1,'rect',C.gray,11));
lane.forEach((a,i)=>edge(a,ends[i],{from:'bottom',to:'top',color:C.gray,width:.8,dash:'dashed'}));
const steps=[[1,2,'定时派发',80],[2,0,'增量轮询',108],[0,2,'公告内容',138],[2,3,'RawEvent',168],[3,4,'归一结果',198],[4,5,'富化产出',228],[5,6,'校验通过',258],[6,7,'影响评估',288],[7,8,'经 Critic 返回',326]];
for(const [i,j,t,y] of steps){let a=box('',35+i*66,y,1,1,'rect',C.main,10.67),b=box('',35+j*66,y,1,1,'rect',C.main,10.67);edge(a,b);label(t,Math.min(i,j)*66+12,y-22,Math.max(90,Math.abs(i-j)*66+46),20,10.67);}
note('演示注入 / 自有仓库 webhook 验签后触发立即 poll；DEMO 单列',369);

slide('F-05');
const r1=row(['编码智能体','/mcp','intel-core'],25,{h:48,kind:'api',color:C.eco});
label('凭据 / scope / 限流 / 审计',365,80,215,24,12);
const d=box('耗时估计',390,125,142,70,'decision');edge(r1[2],d,{from:'bottom',to:'top'});
const sync=box('同步求解\n版本 / QA + Critic',44,146,220,58,'agent',C.agent);edge(d,sync);label('≤60 s',275,144,100);
const async=box('TaskHandle\nget_task_result',390,245,160,52,'api',C.eco);edge(d,async);label('>60 s',438,207,80);
const filter=box('合规过滤',55,269,140,46);edge(sync,filter);
const cut=box('结果裁剪\n≤8k tokens',235,269,124,46);edge(filter,cut);edge(async,cut);
const ret=box('返回 / 分页续取',223,349,154,42,'api',C.eco);edge(cut,ret);

slide('F-06');
const hub=box('Orchestrator',233,17,134,49,'hub',C.agent);
const r=row(['Collector','Triage','Enricher','Critic','GraphWriter'],117,{gap:16,h:50,kind:'agent',color:C.agent,size:12});
edge(hub,r[0],{kind:'straight',from:'bottom',to:'top',width:1.33});
const assess=box('Assessor',445,235,129,46,'agent',C.agent);edge(r[4],assess);
const qa6=box('QA',25,235,128,46,'agent',C.agent);const rep=box('Reporter',235,235,128,46,'agent',C.agent);
edge(qa6,r[3],{kind:'elbow',color:C.agent,dash:'dashDot',width:1.33});edge(rep,r[3],{color:C.agent,dash:'dashDot',width:1.33});edge(assess,r[3],{color:C.agent,dash:'dashDot',width:1.33});
const dlq=box('DLQ\n失败任务',28,327,126,48,'db',C.bad);label('调度器重放',25,295,130,24,12,C.bad);
label('所有对外产出经 Critic\n角色通过数据与任务状态交接',190,324,375,55,13);

slide('F-07');
const q=box('queued',30,40,120,44);const running7=box('running',240,40,120,44);const suc=box('succeeded',450,40,120,44);edge(q,running7);edge(running7,suc);
const retry=box('retrying\n内部状态',240,162,120,50,'rect',C.bad,14,'white','dashed');edge(running7,retry,{color:C.bad,dash:'dashed'});label('429 / 5xx / 超时',224,104,158,26,12);
const dlq7=box('DLQ',240,285,120,46,'db',C.bad);edge(retry,dlq7,{color:C.bad,dash:'dashed'});label('超过 6 次',243,224,114,24,12);
const fail=box('failed',30,162,120,50,'rect',C.bad);edge(running7,fail,{kind:'elbow',color:C.bad,dash:'dashed'});label('4xx（非 429）',21,223,147,25,12);
const exp=box('expired',450,162,120,50);edge(suc,exp);label('结果保留 24 h',440,104,140,24,12);
edge(dlq7,running7,{kind:'elbow',from:'right',to:'right',color:C.bad,dash:'dashed'});label('每 15 min 重放',383,274,192,29,12);
note('retrying 与死信对外均显示为 running');

slide('F-08');
const input=box('富化 / 评估 / 问答 / 报告',125,20,350,42,'agent',C.agent);
const checks=row(['引用\n可回溯','置信度\n达门槛','无违规\n内容'],105,{kind:'decision',h:75,size:13});edge(input,checks[0],{kind:'elbow'});
const verdict8=box('综合校验结论',220,207,160,33,'rect',C.agent,13);edge(checks[2],verdict8,{kind:'elbow',color:C.agent,dash:'dashDot',width:1.33});
const outs=row(['pass\n写入或返回','partial\n标明不受支持句','reject / fail\n重新检索或富化'],260,{chain:false,h:63,color:C.agent,size:13});
outs.forEach(n=>edge(verdict8,n,{color:C.agent,dash:'dashDot',width:1.33}));
note('关系边门槛 0.6；问答 partial 比例 ≤30%；LLM 产出 20% 抽检');

slide('F-09');
const cols=[['一级 官方\n权重 1.0','NVD / GHSA reviewed\nOSV / KEV / EPSS\nATLAS / 厂商公告\nCNNVD / 标准法规\nCNVD：人工导入'],['二级 专业平台\n权重 0.7','huntr / AVID\nGHSA unreviewed\n\n测绘平台仅供暴露面\n不增加来源类别'],['三级 研究资讯\n权重 0.4','arXiv\n安全博客 RSS\n\n仅三级支撑：unconfirmed\n不进入高危告警']];
cols.forEach((v,i)=>{group(v[0],18+i*193,25,178,321);label(v[1],26+i*193,99,162,221,13);});note('平台审核只可下调可信度；CNNVD 主力，CNVD 加分项');

slide('F-10');
const cadence=[['事件','自有仓库 / DEMO','≤1 min'],['5 min','P0 厂商公告','≤10 min'],['10 min','GHSA / NVD / RSS','≤15 / 30 / 30 min'],['15 min','OSV','≤30 min'],['1 h','huntr / KEV','≤2 h'],['6 h','AVID','≤6 h'],['1 d','EPSS / arXiv / CNNVD','≤24 h'],['1 周','标准法规 / CNVD','版本监测 / 人工']];
cadence.forEach((r,i)=>{let y=10+i*43;box(r[0],18,y,80,34,'external',C.main,13,C.light);box(r[1],112,y,245,34,'rect',C.main,13);box(i<7?`目标值 ${r[2]}（待测）`:r[2],370,y,210,34,'rect',i<7?C.warn:C.gray,12,'white',i<7?'dashed':'solid');});
note('6 h 端到端口径：NVD、GHSA、OSV、厂商公告、huntr 首次发现；其余单列',365);

slide('F-11');
let d11=[box('同源幂等\n(source, external_id)',85,18,430,68),box('跨源别名并查集\nCVE > GHSA > OSV > huntr > SW',110,124,380,68),box('无编号相似候选\npurl + SimHash ≥0.9 + 日期 ±3 天',135,230,330,68)];edge(d11[0],d11[1]);edge(d11[1],d11[2]);
box('双 CVE 不合并\nDUPLICATE_OF 候选',22,327,253,60,'rect',C.warn,13,'white','dashed');const c11=box('Critic 复核\n候选不自动合并',325,327,253,60,'agent',C.agent,13);edge(d11[2],c11);

slide('F-12');
const dims=[['CVSS','NVD / GHSA，保留分歧'],['EPSS','FIRST，每日更新'],['KEV','仅 KEV 置位'],['CWE','来源字段与规则'],['ATLAS','规则召回 + LLM'],['受影响与修复版本','OSV 区间语义'],['论文与文章','嵌入 + 组件共现'],['PoC 存在性','仅链接与标题'],['公网暴露面','仅聚合计数']];
box('漏洞实体 → 九维富化画像',115,13,370,39,'db',C.main);
dims.forEach((v,i)=>{let x=20+(i%3)*193,y=79+Math.floor(i/3)*91;let co=[4,6].includes(i)?C.agent:i>=7?C.eco:C.main;box(v[0]+'\n'+v[1],x,y,173,70,'rect',co,13,C.light);});
note('规则 / 确定性：深蓝；弱关联须 Critic：灰紫；合规约束：青灰');

slide('F-13');
const f13=[box('宽口径 823 690\n仅作上限参考',30,25,340,65,'rect',C.gray),box('收窄全球 172 411\n端口 + 响应特征',55,128,290,65),box('国内 51 612\n按平台国家字段',80,231,240,65)];edge(f13[0],f13[1]);edge(f13[1],f13[2]);
box('元数据抽样\n44 / 50 命中\n精确率 88% ≥80%\nverified',391,107,183,147,'rect',C.ok,14,C.light);
label('计数：15:57',70,306,250,26,12);label('抽样：19:55\n当时总数 172 401',356,271,235,54,12);
note('Quake，2026-10-15；仅计数，无资产明细\nTalos / Shodan 文献对照为 1139 个，覆盖口径不同，不直接比较',343);

function graphFigure(full=false){
const c=box('Vulnerability',222,177,156,54,'db',C.main,14);
const nodes=[['Advisory',30,35,'DESCRIBES'],['Component',419,35,'AFFECTS'],['AtlasTechnique',419,177,'MAPS_TO'],['Paper / Article',419,320,'DISCUSSED_IN'],['PocRef',30,320,'HAS_POC_REF'],['CWE',30,177,'HAS_CWE']];
nodes.forEach(([t,x,y,l],i)=>{let n=box(t,x,y,150,45,'rect',C.main,12);let weak=i===2||i===3;edge(i===0?n:c,i===0?c:n,{color:weak?C.agent:C.main,dash:weak?'dashDot':'solid',width:weak?1.33:2});let lx=i===0?160:i===1?322:i===2?374:i===3?321:i===4?160:158;let ly=i<2?100:i===2?204:i<5?287:204;label(l,lx,ly,110,22,10.67);});
if(full){box('Version',230,25,140,42,'rect',C.main,12);label('区间与修复版本',221,72,157,22,11);box('RiskCategory',225,309,150,37,'rect',C.main,12);box('Regulation',225,371,150,30,'rect',C.main,12);label('GOVERNED_BY',231,345,140,22,10.67);label('IN_CATEGORY',224,256,150,23,10.67);}
else {label('规则理由：aliases 含 CVE\n弱关联：摘要相似 + 组件共现',188,19,221,74,11);label('处置关联：修复 + 缓解模板\n版本求解：清单 × 影响区间',185,332,230,62,11);}
}
slide('F-14');graphFigure(false);
slide('F-15');
const fc15=box('字段候选',215,12,170,35);const specials=row(['KEV 专属','一级撤回','区间互斥','双 CVE'],82,{h:65,kind:'decision',size:13});edge(fc15,specials[0],{from:'bottom',to:'top'});
label('先处理特例：并集、撤回、保留候选',60,155,480,26,13);
const ranks=row(['可信度等级','置信度','更新时间'],209,{h:46});
edge(specials[3],ranks[0],{from:'bottom',to:'top'});
const win=box('主值 + provenance',40,308,240,48);const lost=box('落选值 → conflicts[]',322,308,240,48,'rect',C.eco);edge(ranks[2],win,{from:'bottom',to:'top'});edge(ranks[2],lost,{from:'bottom',to:'top'});
note('CVSS 10.0 与 9.8 均保留；主值选择不抹去分歧');

slide('F-16');
const inputs16=row(['依赖文件 / 清单','purl 与生态'],20,{x:100,w:400,h:45,size:13});
const solver16=box('OSV 区间求解',195,108,210,42);edge(inputs16[1],solver16,{from:'bottom',to:'top'});
label('introduced / fixed / last_affected / limit',90,155,420,28,13);
const outcomes=row(['受影响','未发现已知影响','组件未收录'],220,{chain:false,h:48,size:13});
outcomes.forEach(n=>edge(solver16,n,{from:'bottom',to:'top'}));
box('共享入口：Web / check_stack / shaowang check',25,315,550,43,'api',C.eco,14);
note('区间有分歧时提示；高危退出码 1 可接 CI；未知不等于安全');

slide('F-17');
const plan=box('问题与规划器',20,155,110,56,'agent',C.agent,13);
const rr=['BM25','向量 top-50','图扩展 1–2 跳'].map((t,i)=>box(t,164,57+i*88,130,48,'rect',C.main,13));rr.forEach(n=>edge(plan,n));
const rrf=box('RRF\nk=60',330,155,100,56);rr.forEach(n=>edge(n,rrf));
const re=box('前 50 重排\n8–12 证据块',465,155,115,56);edge(rrf,re);
const gen=box('生成并逐句引用',415,326,165,46,'agent',C.agent,13);edge(re,gen);
const critic=box('Critic',210,326,130,46,'agent',C.agent);edge(gen,critic);
edge(critic,plan,{kind:'elbow',from:'left',to:'bottom',color:C.bad,dash:'dashed',width:1.33});label('fail 重新规划',27,335,156,30,12);note('校验通过后返回答案；三路排名融合，不混加原始分数');

slide('F-18');
const steps18=[['影响哪些漏洞','AFFECTS → vllm','图检索 / 命中 n'],['是否有公开引用','HAS_POC_REF','图过滤 / 命中 n'],['是否在时间内','近 90 天','时间过滤 / 命中 n'],['对应什么技术','MAPS_TO → ATLAS','图扩展 / 命中 n']];
const ns=steps18.map((r,i)=>box(r.join('\n'),16+i*146,107,130,133,'rect',C.main,13,C.light));ns.slice(1).forEach((n,i)=>edge(ns[i],n));
label('近 90 天影响 vLLM 且有公开 PoC 链接的漏洞及其 ATLAS 技术',20,27,560,48,14);
note('reasoning_steps 记录子问题、检索方式、查询语句与命中数\nn 是结构示意占位，不是实测结果',298);

slide('F-19');
group('数据面扩展',12,20,178,338,C.eco);['Source Connector','Enricher','Tool / Skill'].forEach((t,i)=>box(t,27,69+i*65,148,45,'plugin',C.eco,12));box('shaowang-sdk\n签名索引',27,278,148,57,'rect',C.eco,13);
const core19=box('intel-core',223,160,150,61,'api',C.eco);
edge(S.shapes.items.find(x=>x.name==='shaowang-sdk 签名索引'),core19,{kind:'elbow'});
group('智能体接入',411,20,177,338,C.eco);box('MCP / OpenAPI / CLI',422,65,155,45,'api',C.eco,12);box('Agent Plugins 包',422,142,155,43,'plugin',C.eco,12);label('Claude Code / Codex\nCursor / Gemini CLI\nKimi 等：待核实',422,221,155,95,13);
edge(core19,S.shapes.items.find(x=>x.name==='MCP / OpenAPI / CLI'),{kind:'elbow'});note('一个服务层统一鉴权、限流、审计与长任务句柄');

slide('F-20');
const top=row(['Discovered','Validated','Installed'],36,{h:46,size:13});label('清单 / Schema / 签名',161,94,175,30,12);label('管理员审批权限',379,94,191,30,12);
const mid=row(['Loaded','Running','Degraded'],182,{h:46,size:13});edge(top[2],mid[0],{from:'bottom',to:'top'});
const dis=box('Disabled',418,310,150,44,'rect',C.bad,14);edge(mid[2],dis,{color:C.bad,dash:'dashed'});
label('连续失败 ≥3\n或 Schema 违规率 >5%',365,128,224,50,12);label('healthcheck 恢复 → Running',183,260,192,45,11);label('24 h 未恢复\n或 Critic 违规',383,239,210,55,11);
box('升级\nMINOR 热升级 / MAJOR 重审',27,310,300,61,'rect',C.eco,13);

slide('F-21');
label('8 类公开 Schema',10,7,580,26,14,C.eco);
['common','normalized-intel','vulnerability','advisory','component','enrichment','relation','qa-answer'].forEach((t,i)=>box(t,12+i%4*147,42+Math.floor(i/4)*46,135,33,'rect',C.eco,11.5,C.light));
const matrix=[['映射对象','OSV','STIX 2.1','CSAF 2.0'],['标识 / 别名','id / aliases','external_references','cve / ids'],['影响区间','ranges.events','software + relation','product_status'],['处置建议','FIX 引用','course-of-action','remediations'],['ATLAS','无原生项','attack-pattern','notes'],['关系与置信度','无原生项','relationship','无原生项'],['PoC 引用','EVIDENCE 链接','external_references','references']];
matrix.forEach((r,i)=>r.forEach((t,j)=>box(t,12+j*144,150+i*31,144,31,'rect',C.main,i===0?12:10.67,i===0?C.light:'white')));
note('按映射表保留语义；没有原生字段的内容使用扩展，不能宣称天然无损',380);

slide('F-22');
const stack=[['采集','Python / httpx（建议）','requests / Scrapy'],['消息调度','Redis Streams / NATS','Kafka'],['编排','LangGraph','AutoGen / CrewAI'],['模型','Qwen / DeepSeek（建议）','私有化模型'],['主存储','PostgreSQL + pgvector','Milvus'],['图谱与检索','Neo4j / OpenSearch + IK','AGE / Meilisearch'],['嵌入与重排','bge-m3 / bge-reranker','商用嵌入'],['后端与 MCP','FastAPI / 官方 Python SDK','Litestar / FastMCP'],['前端','React / ECharts / Cytoscape','Vue / AntV G6'],['可观测','Langfuse / Prometheus / Grafana','OpenTelemetry 后端'],['部署','docker compose','Kubernetes / Helm']];
stack.forEach((r,i)=>{let y=10+i*34;box(r[0],14,y,94,30,'rect',C.main,12,C.light);box(r[1],108,y,300,30,'rect',C.main,12);label(r[2],413,y,175,30,11);});note('右列为备选；建议项与规划项不等于已经部署',385);

slide('F-23');
group('应用容器',20,25,560,115);row(['api\n/api/v1','mcp\n/mcp','workers\n9 个角色','scheduler','web'],70,{x:32,w:536,h:50,gap:11,chain:false,size:12});
group('数据容器',20,178,560,112,C.store);row(['postgres\npgvector','neo4j','opensearch\nIK','redis / nats','minio'],219,{x:32,w:536,h:48,gap:11,chain:false,size:12,kind:'db',color:C.store});
group('可观测容器',20,326,560,75);row(['langfuse','prometheus','grafana'],356,{x:55,w:490,h:32,chain:false,size:12});label('网络与消息队列',150,142,300,31,13);label('调用追踪 / 任务与时效指标',140,291,320,30,13);

slide('F-24');
const v24=box('Vulnerability',218,162,160,48,'db',C.main,14);
const ad24=box('Advisory',20,26,139,38);const co24=box('Component',440,26,140,38);const ve24=box('Version',440,93,140,36);
const at24=box('AtlasTechnique',440,162,140,40,'rect',C.main,12);const cw24=box('CWE',20,162,139,40);
const pa24=box('Paper',440,267,140,37);const ar24=box('Article',440,329,140,37);const po24=box('PocRef',20,267,139,37);
const ri24=box('RiskCategory',218,267,160,37);const re24=box('Regulation',218,329,160,37);
[[ad24,v24],[v24,co24],[v24,at24],[v24,cw24],[v24,pa24],[v24,ar24],[v24,po24],[v24,ri24],[ri24,re24]].forEach(([a,b])=>edge(a,b,{width:1.5}));
label('DESCRIBES',111,96,133,24,11);label('AFFECTS',345,90,103,24,11);label('区间 / fixed',439,67,140,23,11);label('MAPS_TO',363,182,90,22,10.67);label('HAS_CWE',142,182,85,22,10.67);label('DISCUSSED_IN',375,234,145,22,10.67);label('HAS_POC_REF',82,234,150,22,10.67);label('IN_CATEGORY',223,229,150,22,10.67);label('GOVERNED_BY',224,304,150,23,10.67);
label('边属性：reason / confidence / method / created_by_agent',15,382,570,25,11);
S.speakerNotes.append('\nVersion 的关联表达仅说明版本区间，不新增边类型。');
slide('F-25');
const req=box('请求失败',225,16,150,38);const typ=box('错误类型',224,86,152,67,'decision');edge(req,typ);
const retry25=box('429 / 5xx / 超时\n退避重试 ≤6 次',25,205,235,60,'rect',C.bad,13);const hard=box('4xx（非 429）\n直接死信并告警',340,205,235,60,'rect',C.bad,13);edge(typ,retry25,{color:C.bad,dash:'dashed'});edge(typ,hard,{color:C.bad,dash:'dashed'});
const dlq25=box('DLQ / 每 15 min 重放',165,315,270,42,'db',C.bad,13);edge(retry25,dlq25,{color:C.bad,dash:'dashed'});edge(hard,dlq25,{color:C.bad,dash:'dashed'});
note('Retry-After 优先；否则 1 s 起 ×2，上限 5 min，±20% 抖动\n连续 3 周期失败 → degraded → 降级通道',371);

slide('F-26');
group('提供',15,36,165,310,C.eco);label('聚合计数与分布\n\nPoC 链接与标题\n\n修复版本与缓解',23,103,149,210,14);
box('只读服务层\nCritic\n输出过滤',214,142,172,108,'api',C.main,14,C.light);
group('禁止提供',421,36,165,310,C.bad);label('IP / 主机明细\n\n利用代码\n\n执行能力 / 主动扫描',429,103,149,210,14);
note('合规限制在采集、存储、服务与校验多个边界执行');

slide('F-27');
const time27=['source_\npublished_at','first_seen_at','normalized_at','enriched_at','queryable_at'];row(time27,90,{h:55,gap:13,size:11});
box('采集时延 = 首见 − 发布',25,194,210,48,'rect',C.main,13,C.light);box('处理时延 = 可查询 − 首见',248,194,327,48,'rect',C.main,13,C.light);
box('端到端 = 可查询 − 发布；目标值 ≤6 h（待测）',25,279,550,46,'rect',C.warn,14,'white','dashed');note('仅漏洞类首次发现；日更源单列；DEMO 不计\n日期精度不足时按当日零点计，保守高估',365);

slide('F-29');
const innov=[['面向 AI 基础设施的\n垂直多源融合','P0 5 min / 无 CVE 入库','监测 / 时效'],['可解释的\n自动关联推理引擎','边带理由 / Critic 门槛','富化 / 准确'],['从依赖文件出发的\n“我受不受影响”自查','OSV 求解 / 三种结果','富化 / Agent'],['可解释 GraphRAG 问答','三路检索 / 逐句引用','问答 / 准确'],['内部多智能体编排与\n外部 MCP 开放统一','9 角色 / 统一服务层','Agent'],['时效可观测与故障自愈','五段时间戳 / 故障恢复','时效 / 自动化'],['开放的插件生态','8 Schema / 三类扩展点','Agent / 文档']];
innov.forEach((r,i)=>{let y=12+i*53;box(String(i+1),15,y,34,43,'rect',C.main,14,C.light);box(r[0],49,y,158,43,'rect',C.main,13);label(r[1],216,y,235,43,12);label(r[2],462,y,122,43,12);});note('七项创新均以第四章评测验证，当前未测结果保持占位',385);

slide('F-30');
const tests=[['时效','五段时间戳','按源分项','P50 / P95','目标值 ≤6 h\n（待测）'],['富化','200 条金标','Critic 前后','准确率 / κ','目标值 ≥95%\n（待测）'],['问答','约 100 题','三组对照','答案 / 引用','目标值待定\n（待测）'],['自愈','6 个场景','故障注入','成功率 / 恢复','目标值待定\n（待测）'],['兼容','4 类客户端','远程 / stdio','加载 / 续取','目标值待定\n（待测）']];
tests.forEach((r,i)=>{let x=12+i*118;group(r[0],x,29,108,317);r.slice(1,4).forEach((t,j)=>label(t,x+5,91+j*55,98,43,12));box(r[4],x+6,274,96,57,'rect',C.warn,12,'white','dashed');});note('同模型同提示；保存原始结果；未执行不计为通过');

await (await PresentationFile.exportPptx(P)).save(path.join(build,'figures-draft.pptx'));
await fs.writeFile(path.join(build,'slides-order.json'),JSON.stringify(['STYLE',...specs.filter(s=>s.id!=='F-28').map(s=>s.id)],null,2));
console.log('Created',P.slides.items.length,'editable slides');






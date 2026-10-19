import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';

const build=path.dirname(fileURLToPath(import.meta.url));
const specs=JSON.parse(await fs.readFile('D:/dianzi/output/shaowang-report-20261016/build/figures.json','utf8'));
const P=Presentation.create({slideSize:{width:1200,height:840}});
const C={ink:'#233E54',blue:'#277DC3',navy:'#245D8F',sky:'#92C5EC',pale:'#EAF4FC',line:'#A6C4DB',green:'#547D45',mint:'#E5F0DA',gold:'#A67A20',yellow:'#FFF1CB',red:'#AB554B',pink:'#FBE7E2',gray:'#657D8E',fog:'#F3F6F8',white:'#FFFFFF'};
let S; const order=[];
function shape(t,x,y,w,h,{fill=C.pale,line=C.line,color=C.ink,size=23,bold=false,geom='roundRect',align='center',dash='solid',radius=4}={}){
 size=Math.max(size,23);
 const a=S.shapes.add({geometry:geom,name:t.replaceAll('\n',' ').slice(0,90)||'boundary',position:{left:x,top:y,width:w,height:h},fill,line:{fill:line,width:line==='none'?0:1.4,style:dash},borderRadius:geom==='roundRect'?radius:undefined});
 if(t){a.text=t.split('\n').map(line=>({runs:[{run:line,style:{typeface:'Microsoft YaHei',fontSize:`${size}px`,bold}}]}));a.text.style={fontSize:size,bold,color,alignment:align,verticalAlignment:'middle',wrap:'word',insets:3};}
 return a;
}
function text(t,x,y,w,h=36,size=22,color=C.ink,bold=false,align='left'){return shape(t,x,y,w,h,{geom:'textbox',fill:'none',line:'none',size,color,bold,align});}
function lineLabel(t,x,y,w,h=36,size=22,color=C.ink){return shape(t,x,y,w,h,{geom:'textbox',fill:C.white,line:'none',size,color,align:'center'});}
function rect(x,y,w,h,fill,line='none',dash='solid'){return shape('',x,y,w,h,{geom:'rect',fill,line,dash});}
function dot(x,y,r=6,fill=C.blue){return shape('',x-r,y-r,r*2,r*2,{geom:'ellipse',fill,line:'none'});}
function edge(a,b,{from='right',to='left',color=C.blue,dash='solid',arrow=true,width=2.4,kind='straight'}={}){return S.shapes.connect(a,b,{kind,fromSide:from,toSide:to,line:{fill:color,width,style:dash},...(arrow?{tail:{type:'triangle',width:'sm',length:'sm'}}:{})});}
function segment(x1,y1,x2,y2,{color=C.blue,dash='solid',arrow=false,width=2}={}){let a=rect(x1,y1,.1,.1,'none'),b=rect(x2,y2,.1,.1,'none');return edge(a,b,{color,dash,arrow,width});}
function route(points,{color=C.blue,dash='solid',arrow=true,width=2.2}={}){points.slice(1).forEach((p,i)=>segment(...points[i],...p,{color,dash,width,arrow:arrow&&i===points.length-2}));}
function poly(points,fill,line=C.line){const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),x=Math.min(...xs),y=Math.min(...ys),w=Math.max(...xs)-x,h=Math.max(...ys)-y;return S.shapes.add({geometry:'custom',name:'layer surface',position:{left:x,top:y,width:w,height:h},fill,line:{fill:line,width:1},customPaths:[{width:w,height:h,commands:[{moveTo:{x:points[0][0]-x,y:points[0][1]-y}},...points.slice(1).map(p=>({lineTo:{x:p[0]-x,y:p[1]-y}})),{close:{}}]}]});}
function panel(title,x,y,w,h,{fill=C.fog,color=C.blue,dash='solid'}={}){shape('',x,y,w,h,{fill,line:C.line,dash,radius:18});text(title,x+18,y+10,w-36,38,24,color,true);}
function block(title,detail,x,y,w,h,{fill=C.pale,color=C.blue,geom='roundRect',size=25}={}){let a=shape('',x,y,w,h,{fill,line:C.line,geom});let offset=geom==='can'?20:0;text(title,x+10,y+10+offset,w-20,40,size,color,true,'center');if(detail)text(detail,x+12,y+55+offset,w-24,h-65-offset,21,color===C.white?C.white:C.ink,false,'center');return a;}
function footer(t){text(t,45,770,1110,66,23,C.gray,false,'left');}
function slide(id){S=P.slides.add();S.background.fill=C.white;order.push(id);const sp=specs.find(s=>s.id===id);S.speakerNotes.text=`${id} ${sp.title}\n报告位置：${sp.location}\n技术内容沿用 ShaoWang-技术报告.docx 与原图源，依据 design-dossier.md ${sp.source}。设计参数不代表已测或已部署。\n配色与构图参考：CACR2025757WAK 报告图3.1的语义分区；PrivLLM 报告图1.2、图2.1的层叠和蓝绿黄配色；003立体图示模板第25、45、60页。重绘为原生可编辑形状、文本和连接线。`;return S;}
function ribbon(t,x,y,w,color=C.blue){return shape(t,x,y,w,52,{fill:color,line:'none',color:C.white,bold:true,size:25});}
function numbered(n,x,y,color=C.blue){return shape(String(n),x,y,44,44,{geom:'ellipse',fill:color,line:'none',color:C.white,size:20,bold:true});}
function chain(items,y,{x=50,w=1100,h=85,gap=26,fill=C.pale,size=24}={}){let cw=(w-(items.length-1)*gap)/items.length;const nodes=items.map((t,i)=>shape(t,x+i*(cw+gap),y,cw,h,{fill,size,bold:true}));nodes.slice(1).forEach((n,i)=>edge(nodes[i],n));return nodes;}

slide('F-01');
const layers=[['接入层','Web / MCP 7 工具 / OpenAPI\nCLI / Agent Plugins'],['服务层','intel-core    GraphRAG    鉴权与结果裁剪'],['智能体编排层','Orchestrator + 8 个角色    LangGraph'],['知识层','PostgreSQL + pgvector    Neo4j    OpenSearch\nMinIO    Redis Streams 或 NATS JetStream'],['采集层','Connector × N    自有仓库 webhook'],['数据源层','9 类来源    三级可信度    分级轮询']];
layers.forEach(([name,desc],i)=>{let y=132+i*99;poly([[60,y],[870,y],[890,y+18],[80,y+18]],i%2?C.pale:'#D6EAF9');rect(80,y+18,810,69,i===3?'#D8EBCF':i%2?'#ECF5FC':'#E0EFFB',C.line);poly([[60,y],[80,y+18],[80,y+87],[60,y+69]],C.sky);text(name,93,y+30,184,43,24,C.navy,true);text(desc,290,y+22,584,62,23,C.ink);});
['时效可观测','可信与裁决','合规边界','开放生态'].forEach((t,i)=>{shape(t,956,150+i*143,180,104,{fill:i===2?C.yellow:C.pale,bold:true,size:25});});
segment(921,153,921,708,{color:C.line,width:2});segment(31,700,31,173,{arrow:true,width:2});footer('PostgreSQL 是事实源；outbox 同步图库与全文索引');

slide('F-02');
const bMon=block('监测','9 类来源\n持续发现与归一',80,210,270,150);
const bEnr=block('富化','9 个维度\n实体、关系与证据',850,210,270,150,{fill:C.mint,color:C.green});
const bQa=block('问答','逐句引用\n回答与版本自查',465,581,270,150,{fill:C.yellow,color:C.gold});
const bCore=block('知识图谱与事实库','事实版本与可追溯证据',425,324,350,160,{geom:'can'});
route([[350,240],[850,240]]);text('归并后的事件',430,191,340,38,22,C.blue,false,'center');
route([[985,360],[985,656],[735,656]],{color:C.green});route([[465,656],[215,656],[215,360]]);
edge(bMon,bCore,{from:'right',to:'left'});edge(bCore,bEnr,{from:'right',to:'left',color:C.green});edge(bCore,bQa,{from:'bottom',to:'top'});
text('Critic 校验',425,125,350,48,27,C.green,true,'center');text('版本自查',232,492,176,45,25,C.navy,true,'center');text('MCP 开放',793,492,176,45,25,C.navy,true,'center');footer('时效可观测贯穿发现、富化、校验与服务');

slide('F-03');
chain(['采集','归一','富化','校验','存储','服务'],154,{h:94});
const timeXs=[145,370,595,820,1055];segment(145,430,1055,430,{width:4});
['来源发布','首次发现','完成归一','完成富化','可查询'].forEach((t,i)=>{dot(timeXs[i],430,9);text(t,timeXs[i]-96,360,192,45,25,C.navy,true,'center');});
['source_\npublished_at','first_seen_at','normalized_at','enriched_at','queryable_at'].forEach((t,i)=>text(t,timeXs[i]-112,458,224,72,23,C.gray,false,'center'));
shape('采集时延',70,548,240,66,{fill:C.pale,bold:true});shape('处理时延',330,548,800,66,{fill:C.mint,color:C.green,bold:true});
shape('端到端时延目标值 ≤6 h（待测）',70,665,1060,68,{fill:C.yellow,color:C.gold,bold:true,size:28});footer('漏洞类首次发现纳入统计；日更源单列；DEMO 不计');

slide('F-04');
const lanes=['厂商仓库','编排器','采集器','归一器','富化器','校验器','图写入器','评估器','编码\n智能体'];
const lx=lanes.map((_,i)=>74+i*131.5);
lanes.forEach((t,i)=>{shape(t,lx[i]-60,120,120,62,{fill:i===0||i===8?C.yellow:C.pale,size:24,bold:true});segment(lx[i],190,lx[i],666,{color:C.line,dash:'dashed',width:1.2});});
const seq=[[1,2,'定时派发'],[2,0,'增量轮询'],[0,2,'公告内容'],[2,3,'RawEvent'],[3,4,'归一结果'],[4,5,'富化产出'],[5,6,'校验通过'],[6,7,'影响评估'],[7,8,'经校验返回']];
seq.forEach(([a,b,t],i)=>{let y=230+i*52;segment(lx[a],y,lx[b],y,{arrow:true,color:i>=6?C.green:C.blue});text(t,Math.min(lx[a],lx[b])-15,y-34,Math.abs(lx[a]-lx[b])+30,32,23,C.ink,false,'center');});
text('编排器 Orchestrator    采集器 Collector    归一器 Triage',50,684,1100,34,23);
text('富化器 Enricher    校验器 Critic    图写入器 GraphWriter    评估器 Assessor',50,726,1100,34,23);
footer('演示注入 / 自有仓库 webhook 验签后触发立即 poll；DEMO 单列');

slide('F-05');
chain(['编码智能体','/mcp','intel-core'],132,{x:65,w:1070,h:68,gap:80});text('凭据 / scope / 限流 / 审计',552,211,425,39,21,C.gray,false,'center');
const dec=shape('耗时估计',745,282,280,126,{geom:'diamond',fill:C.yellow,color:C.gold,size:26,bold:true});route([[994,200],[994,250],[885,250],[885,282]]);
const sync=block('同步求解','版本 / QA + Critic',72,318,360,134);edge(dec,sync,{from:'left',to:'right'});text('≤60 s',475,320,195,40,24,C.blue,true,'center');
const async=block('TaskHandle','get_task_result',745,488,280,126,{fill:C.mint,color:C.green});edge(dec,async,{from:'bottom',to:'top'});text('>60 s',1000,421,136,40,24,C.green,true);
const fil=shape('合规过滤',72,540,230,65,{fill:C.pale,bold:true});edge(sync,fil,{from:'bottom',to:'top'});
const cut=shape('结果裁剪\n≤8k tokens',389,530,245,85,{fill:C.pale,bold:true});edge(fil,cut);edge(async,cut,{from:'left',to:'right'});
const ret=shape('返回 / 分页续取',389,674,424,65,{fill:C.blue,line:'none',color:C.white,bold:true});edge(cut,ret,{from:'bottom',to:'top'});

slide('F-06');
const orchestrator=shape('Orchestrator',440,124,320,82,{geom:'hexagon',fill:C.blue,color:C.white,line:'none',bold:true,size:28});
const main=chain(['Collector','Triage','Enricher','Critic','GraphWriter'],320,{x:45,w:1110,h:83,gap:30,size:24});
route([[600,206],[600,259],[150,259],[150,320]]);text('任务调度',302,222,200,34,20,C.gray);
const qa=block('QA','问答产出',100,515,235,106,{fill:C.yellow,color:C.gold});const reporter=block('Reporter','报告产出',481,515,235,106,{fill:C.yellow,color:C.gold});const assessor=block('Assessor','影响评估',862,515,235,106,{fill:C.mint,color:C.green});
edge(main[4],assessor,{from:'bottom',to:'top'});route([[217,515],[217,466],[831,466],[831,403]],{dash:'dashed',color:C.green});route([[598,515],[598,466]],{dash:'dashed',color:C.green,arrow:false});route([[980,515],[980,466],[831,466]],{dash:'dashed',color:C.green,arrow:false});
shape('DLQ 失败任务',100,681,235,57,{geom:'can',fill:C.pink,color:C.red,size:22,bold:true});text('调度器重放',352,685,210,45,22,C.red);text('所有对外产出均经 Critic 校验',588,678,518,55,24,C.green,true,'center');footer('9 个角色通过数据与任务状态交接');

slide('F-07');
const q=shape('queued',65,167,255,77,{bold:true});const run=shape('running',475,167,255,77,{fill:C.blue,color:C.white,line:'none',bold:true});const suc=shape('succeeded',885,167,255,77,{fill:C.mint,color:C.green,bold:true});edge(q,run);edge(run,suc,{color:C.green});
const retry=block('retrying','内部状态',475,370,255,110,{fill:C.yellow,color:C.gold});edge(run,retry,{from:'bottom',to:'top',color:C.gold,dash:'dashed'});lineLabel('429 / 5xx / 超时',451,285,295,40,22,C.gold);
const fail=shape('failed',65,387,255,77,{fill:C.pink,color:C.red,bold:true});route([[475,229],[392,229],[392,425],[320,425]],{color:C.red,dash:'dashed'});text('4xx（非 429）',70,483,250,42,22,C.red,false,'center');
const expire=shape('expired',885,387,255,77,{fill:C.fog,color:C.gray,bold:true});edge(suc,expire,{from:'bottom',to:'top',color:C.gray});lineLabel('结果保留 24 h',886,288,254,40,22,C.gray);
const dlq=shape('DLQ',475,623,255,76,{geom:'can',fill:C.pink,color:C.red,bold:true});edge(retry,dlq,{from:'bottom',to:'top',color:C.red,dash:'dashed'});lineLabel('超过 6 次',499,537,210,40,22,C.red);route([[730,661],[808,661],[808,278],[664,278],[664,244]],{color:C.red,dash:'dashed'});text('每 15 min 重放',850,591,290,70,23,C.red,false,'center');footer('retrying 与死信对外均显示为 running');

slide('F-08');
shape('富化 / 评估 / 问答 / 报告',250,130,700,65,{fill:C.blue,color:C.white,line:'none',size:28,bold:true});
const checks=chain(['引用可回溯','置信度达门槛','无违规内容'],274,{x:115,w:970,h:90,gap:55,fill:C.pale});route([[600,195],[600,231],[258,231],[258,274]]);
const result=shape('综合校验结论',440,435,320,65,{fill:C.mint,color:C.green,bold:true});route([[943,364],[943,403],[600,403],[600,435]],{color:C.green});
const outcomes=[block('pass','写入或返回',50,601,330,125,{fill:C.mint,color:C.green}),block('partial','标明不受支持句',435,601,330,125,{fill:C.yellow,color:C.gold}),block('reject / fail','重新检索或富化',820,601,330,125,{fill:C.pink,color:C.red})];
outcomes.forEach((n,i)=>route([[600,500],[600,547],[215+385*i,547],[215+385*i,601]],{color:[C.green,C.gold,C.red][i]}));footer('关系边门槛 0.6；问答 partial 比例 ≤30%；LLM 产出 20% 抽检');

slide('F-09');
const tiers=[{x:50,w:350,n:'一级 官方',weight:'1.0',color:C.blue,fill:C.pale,body:'NVD / GHSA reviewed\nOSV / KEV / EPSS\nATLAS / 厂商公告\nCNNVD / 标准法规\nCNVD：人工导入'}, {x:425,w:350,n:'二级 专业平台',weight:'0.7',color:C.green,fill:C.mint,body:'huntr / AVID\nGHSA unreviewed\n\n测绘平台仅供暴露面\n不增加来源类别'}, {x:800,w:350,n:'三级 研究资讯',weight:'0.4',color:C.gold,fill:C.yellow,body:'arXiv\n安全博客 RSS\n\n仅三级支撑：unconfirmed\n不进入高危告警'}];
tiers.forEach(v=>{shape('',v.x,164,v.w,541,{fill:v.fill,line:'none',radius:20});ribbon(v.n,v.x+20,186,v.w-40,v.color);text(v.weight,v.x+20,259,v.w-40,99,62,v.color,true,'center');text('可信度权重',v.x+20,356,v.w-40,36,20,v.color,false,'center');text(v.body,v.x+15,422,v.w-30,253,22,C.ink,false,'center');});footer('平台审核只可下调可信度；CNNVD 主力，CNVD 加分项');

slide('F-10');
text('轮询频率',68,121,190,42,25,C.blue,true);text('来源与触发方式',315,121,450,42,25,C.blue,true);text('发现时延目标（待测）',807,121,350,42,25,C.gold,true);
const cadence=[['事件','自有仓库 / DEMO','≤1 min'],['5 min','P0 厂商公告','≤10 min'],['10 min','GHSA / NVD / RSS','≤15 / 30 / 30 min'],['15 min','OSV','≤30 min'],['1 h','huntr / KEV','≤2 h'],['6 h','AVID','≤6 h'],['1 d','EPSS / arXiv / CNNVD','≤24 h'],['1 周','标准法规 / CNVD','版本监测 / 人工']];
cadence.forEach((r,i)=>{let y=184+i*68;rect(50,y,1100,59,i%2?C.white:C.fog);shape(r[0],65,y+4,180,51,{fill:i<4?C.blue:C.pale,color:i<4?C.white:C.navy,line:'none',bold:true,size:23});text(r[1],310,y+5,495,49,23);text(r[2],812,y+5,330,49,24,i<7?C.gold:C.gray,true);});footer('6 h 口径：NVD、GHSA、OSV、厂商公告、huntr 首次发现；其余单列');

slide('F-11');
const dedup=[['同源幂等','(source, external_id)',140,142,920],['跨源别名并查集','CVE > GHSA > OSV > huntr > SW',205,314,790],['无编号相似候选','purl + SimHash ≥0.9 + 日期 ±3 天',270,486,660]];
dedup.forEach(([t,d,x,y,w],i)=>{poly([[x,y],[x+w,y],[x+w-36,y+122],[x+36,y+122]],i===2?C.mint:C.pale);text(t,x+45,y+14,w-90,43,29,i===2?C.green:C.blue,true,'center');text(d,x+40,y+65,w-80,42,23,C.ink,false,'center');if(i<2)segment(600,y+125,600,y+165,{arrow:true});});
shape('双 CVE 不合并\n保留 DUPLICATE_OF 候选',65,660,470,79,{fill:C.yellow,color:C.gold,bold:true,size:22});shape('Critic 复核\n候选不自动合并',665,660,470,79,{fill:C.mint,color:C.green,bold:true,size:23});route([[600,608],[600,634],[900,634],[900,660]],{color:C.green});

slide('F-12');
ribbon('漏洞实体',440,127,320);segment(600,179,600,220,{arrow:true});
const dimensions=[['CVSS','NVD / GHSA\n保留分歧'],['EPSS','FIRST\n每日更新'],['KEV','仅 KEV 置位'],['CWE','来源字段与规则'],['ATLAS','规则召回 + LLM'],['受影响与修复版本','OSV 区间语义'],['论文与文章','嵌入 + 组件共现'],['PoC 存在性','仅链接与标题'],['公网暴露面','仅聚合计数']];
dimensions.forEach(([t,d],i)=>{let x=50+(i%3)*385,y=240+Math.floor(i/3)*166;let special=[4,6].includes(i),limited=i>=7;block(t,d,x,y,330,140,{fill:limited?C.yellow:special?C.mint:C.pale,color:limited?C.gold:special?C.green:C.blue,size:24});numbered(i+1,x-2,y-16,limited?C.gold:special?C.green:C.blue);});footer('蓝色：规则与确定性信息；绿色：弱关联须 Critic 校验；黄色：合规边界');

slide('F-13');
text('Quake 暴露面口径收窄',65,121,650,50,28,C.blue,true);
const funnels=[{x:65,y:199,w:660,t:'823 690',d:'宽口径，仅作上限参考',fill:C.fog,color:C.gray},{x:115,y:378,w:560,t:'172 411',d:'收窄全球：端口 + 响应特征',fill:C.pale,color:C.blue},{x:175,y:557,w:440,t:'51 612',d:'国内：按平台国家字段',fill:C.mint,color:C.green}];
funnels.forEach((v,i)=>{poly([[v.x,v.y],[v.x+v.w,v.y],[v.x+v.w-45,v.y+133],[v.x+45,v.y+133]],v.fill);text(v.t,v.x+40,v.y+10,v.w-80,65,46,v.color,true,'center');text(v.d,v.x+15,v.y+77,v.w-30,42,22,C.ink,false,'center');if(i<2)segment(395,v.y+138,395,v.y+172,{arrow:true});});
panel('元数据抽样验证',795,199,345,491,{fill:C.yellow,color:C.gold});text('44 / 50',814,284,307,80,48,C.gold,true,'center');text('精确率 88% ≥80%\nverified',814,389,307,84,27,C.green,true,'center');text('抽样时间 19:55\n当时总数 172 401',811,522,313,94,22,C.ink,false,'center');
text('计数时间 15:57',105,706,580,39,20,C.gray,false,'center');footer('2026-10-15，仅计数；Talos / Shodan 文献为 1139，覆盖口径不同，不直接比较');

slide('F-14');
const center14=block('Vulnerability','漏洞事实',425,337,350,120,{fill:C.blue,color:C.white});
const graphNodes=[['Advisory','公告',55,130,'描述',false],['Component','组件',875,130,'影响',false],['CWE','弱点分类',55,337,'弱点',false],['AtlasTechnique','攻击技术',875,337,'映射',true],['PocRef','公开引用',55,548,'引用',false],['Paper / Article','论文与文章',875,548,'讨论',true]];
graphNodes.forEach(([t,d,x,y,rel,weak],i)=>{block(t,d,x,y,270,114,{fill:weak?C.mint:C.pale,color:weak?C.green:C.blue,size:24});let ex=x<400?325:875,sx=x<400?425:775,bx=x<400?375:825,py=i<2?360:i<4?397:434;route(i===0?[[ex,y+57],[bx,y+57],[bx,py],[sx,py]]:[[sx,py],[bx,py],[bx,y+57],[ex,y+57]],{color:weak?C.green:C.blue,dash:weak?'dashed':'solid'});lineLabel(rel,x<400?329:779,y+17,92,38,23,weak?C.green:C.blue);});
text('规则理由：aliases 含 CVE',390,140,420,46,24,C.blue,false,'center');text('弱关联：摘要相似 + 组件共现',385,205,430,68,23,C.green,false,'center');text('处置关联：修复 + 缓解模板\n版本求解：清单 × 影响区间',380,540,440,98,24,C.ink,false,'center');
text('描述 DESCRIBES    影响 AFFECTS    弱点 HAS_CWE',50,690,1100,34,23);
text('映射 MAPS_TO    引用 HAS_POC_REF    讨论 DISCUSSED_IN',50,730,1100,34,23);
footer('实线：确定性关联；虚线：须经 Critic 校验的弱关联');

slide('F-15');
ribbon('字段候选',450,127,300);segment(600,179,600,227,{arrow:true});
panel('优先处理特例',50,225,1100,173,{fill:C.yellow,color:C.gold});
['KEV 专属','一级撤回','区间互斥','双 CVE'].forEach((t,i)=>shape(t,80+i*274,294,230,64,{fill:C.white,line:'#DEC989',size:25,bold:true,color:C.gold}));
text('并集、撤回、保留候选',365,412,470,42,24,C.gold,false,'center');
const ranks=chain(['可信度等级','置信度','更新时间'],491,{x:100,w:1000,h:72,gap:54});route([[600,454],[600,474],[254,474],[254,491]]);
const win=shape('主值 + provenance',75,663,470,77,{fill:C.pale,bold:true,size:26});const conflicts=shape('落选值保留在 conflicts[]',655,663,470,77,{fill:C.mint,color:C.green,bold:true,size:25});route([[946,563],[946,613],[310,613],[310,663]]);route([[946,613],[890,613],[890,663]],{color:C.green});footer('CVSS 10.0 与 9.8 均保留；主值选择不抹去分歧');

slide('F-16');
const in1=block('依赖文件 / 清单','组件与版本',100,144,440,126);const in2=block('purl 与生态','规范化输入',660,144,440,126);
const solver=block('OSV 区间求解','introduced / fixed / last_affected / limit',240,365,720,130,{fill:C.blue,color:C.white});route([[320,270],[320,315],[600,315],[600,365]]);route([[880,270],[880,315],[600,315]],{arrow:false});
['受影响','未发现已知影响','组件未收录'].forEach((t,i)=>{let x=50+385*i;shape(t,x,588,330,82,{fill:[C.pink,C.mint,C.yellow][i],color:[C.red,C.green,C.gold][i],bold:true,size:25});route([[600,495],[600,541],[x+165,541],[x+165,588]],{color:[C.red,C.green,C.gold][i]});});
text('共享入口：Web / check_stack / shaowang check',75,699,1050,49,26,C.blue,true,'center');footer('区间有分歧时提示；高危退出码 1 可接 CI；未知不等于安全');

slide('F-17');
const query=block('问题与规划器','检索计划',45,331,220,125);
const retrievers=[block('BM25','关键词召回',345,147,265,108),block('向量 top-50','语义召回',345,340,265,108),block('图扩展 1–2 跳','关系召回',345,533,265,108,{fill:C.mint,color:C.green})];
retrievers.forEach((n,i)=>route([[265,394],[303,394],[303,201+193*i],[345,201+193*i]],{color:i===2?C.green:C.blue}));
const fusion=block('RRF','k=60',699,331,175,125);retrievers.forEach((n,i)=>route([[610,201+193*i],[653,201+193*i],[653,394],[699,394]],{color:i===2?C.green:C.blue}));
const rerank=block('前 50 重排','8–12 证据块',935,331,220,125);edge(fusion,rerank);
const generate=shape('生成并逐句引用',828,650,327,70,{fill:C.yellow,color:C.gold,bold:true,size:25});edge(rerank,generate,{from:'bottom',to:'top'});
const critic=shape('Critic 校验',405,650,262,70,{fill:C.mint,color:C.green,bold:true,size:26});edge(generate,critic,{from:'left',to:'right',color:C.green});route([[405,685],[155,685],[155,456]],{color:C.red,dash:'dashed'});lineLabel('fail 重新规划',53,592,243,43,21,C.red);footer('三路排名融合，不混加原始分数；校验通过后返回答案');

slide('F-18');
shape('近 90 天影响 vLLM 且有公开 PoC 链接的漏洞及其 ATLAS 技术',50,128,1100,94,{fill:C.blue,color:C.white,line:'none',size:27,bold:true});
const hops=[['影响哪些漏洞','AFFECTS\nvllm','图检索 / 命中 n'],['是否有公开引用','HAS_POC_REF','图过滤 / 命中 n'],['是否在时间内','近 90 天','时间过滤 / 命中 n'],['对应什么技术','MAPS_TO\nATLAS','图扩展 / 命中 n']];
hops.forEach((v,i)=>{let x=50+i*284;numbered(i+1,x+92,283,i===3?C.green:C.blue);text(v[0],x,350,248,60,26,C.navy,true,'center');shape(v[1],x+10,437,228,115,{fill:i===3?C.mint:C.pale,color:i===3?C.green:C.blue,size:25,bold:true});text(v[2],x,586,248,60,22,C.gray,false,'center');if(i<3)segment(x+238,494,x+284,494,{arrow:true});});
footer('reasoning_steps 保存子问题、检索方式、查询语句与命中数；n 是示意占位，非实测');

slide('F-19');
panel('数据面扩展',45,142,335,530,{fill:C.pale});
['Source Connector','Enricher','Tool / Skill'].forEach((t,i)=>shape(t,72,226+i*98,281,68,{geom:'parallelogram',fill:C.white,size:24,bold:true}));
shape('shaowang-sdk\n签名索引',72,541,281,94,{fill:C.blue,color:C.white,line:'none',size:25,bold:true});
const core=block('intel-core','统一服务层',450,348,300,139,{geom:'hexagon',fill:C.mint,color:C.green,size:32});
panel('智能体接入',820,142,335,530,{fill:C.pale});shape('MCP / OpenAPI / CLI',841,226,293,76,{fill:C.white,size:23,bold:true});shape('Agent Plugins 包',841,350,293,76,{geom:'parallelogram',fill:C.white,size:24,bold:true});text('Claude Code / Codex\nCursor / Gemini CLI\nKimi 等：待核实',843,489,290,143,22,C.ink,false,'center');
route([[353,588],[414,588],[414,417],[450,417]]);route([[750,417],[783,417],[783,264],[841,264]]);footer('统一鉴权、限流、审计与长任务句柄');

slide('F-20');
const top20=chain(['Discovered','Validated','Installed'],154,{x:70,w:1060,h:80,gap:125,size:28});text('清单 / Schema / 签名',235,263,330,55,23,C.gray,false,'center');text('管理员审批权限',703,263,330,55,23,C.gray,false,'center');
const loaded=shape('Loaded',70,422,270,80,{bold:true,size:28});const running20=shape('Running',465,422,270,80,{fill:C.mint,color:C.green,bold:true,size:28});const degraded=shape('Degraded',860,422,270,80,{fill:C.yellow,color:C.gold,bold:true,size:28});edge(loaded,running20,{color:C.green});edge(running20,degraded,{color:C.gold});route([[995,234],[995,345],[205,345],[205,422]]);
text('连续失败 ≥3 或 Schema 违规率 >5%',580,363,560,45,22,C.gold,false,'center');route([[995,502],[995,589],[600,589],[600,502]],{color:C.green,dash:'dashed'});text('healthcheck 恢复',580,601,280,39,22,C.green,false,'center');
shape('Disabled',860,678,270,65,{fill:C.pink,color:C.red,bold:true,size:28});route([[1130,462],[1162,462],[1162,710],[1130,710]],{color:C.red,dash:'dashed'});text('24 h 未恢复\n或 Critic 违规',836,608,300,66,20,C.red,false,'center');
shape('升级\nMINOR 热升级 / MAJOR 重审',70,647,500,96,{fill:C.pale,size:24,bold:true});

function nativeTable(values,x,y,w,h,widths,size=23){
 size=Math.max(size,23);
 const table=S.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values:values.map((row,r)=>row.map(value=>[{runs:[{run:value,style:{typeface:'Microsoft YaHei',fontSize:`${size}px`,bold:r===0}}]}]))});
 table.borders.assign({fill:C.line,width:1,style:'solid'});
 values.forEach((row,r)=>{table.rows[r].height=h/values.length;row.forEach((_,c)=>{const cell=table.getCell(r,c);cell.fill=r===0?C.blue:r%2?C.pale:C.white;cell.text.style={fontSize:size,bold:r===0,color:r===0?C.white:C.ink,alignment:c===0?'left':'center',verticalAlignment:'middle',insets:4,wrap:'word'};});});
 return table;
}

slide('F-21');
text('8 类公开 Schema',50,117,1100,44,27,C.blue,true);
['common','normalized-intel','vulnerability','advisory','component','enrichment','relation','qa-answer'].forEach((t,i)=>shape(t,50+i%4*282,179+Math.floor(i/4)*68,254,52,{fill:C.pale,line:'none',size:22,bold:true}));
nativeTable([['映射对象','OSV','STIX 2.1','CSAF 2.0'],['标识 / 别名','id / aliases','external_references','cve / ids'],['影响区间','ranges.events','software + relation','product_status'],['处置建议','FIX 引用','course-of-action','remediations'],['ATLAS','无原生项','attack-pattern','notes'],['关系与置信度','无原生项','relationship','无原生项'],['PoC 引用','EVIDENCE 链接','external_references','references']],50,350,1100,385,[245,260,330,265],22);
footer('按映射表保留语义；没有原生字段的内容使用扩展，不能宣称天然无损');

slide('F-22');
const stack=[['层次','报告方案','备选'],['采集','Python / httpx（建议）','requests / Scrapy'],['消息调度','Redis Streams / NATS','Kafka'],['编排','LangGraph','AutoGen / CrewAI'],['模型','Qwen / DeepSeek（建议）','私有化模型'],['主存储','PostgreSQL + pgvector','Milvus'],['图谱与检索','Neo4j / OpenSearch + IK','AGE / Meilisearch'],['嵌入与重排','bge-m3 / bge-reranker','商用嵌入'],['后端与 MCP','FastAPI / 官方 Python SDK','Litestar / FastMCP'],['前端','React / ECharts / Cytoscape','Vue / AntV G6'],['可观测','Langfuse / Prometheus / Grafana','OpenTelemetry 后端'],['部署','docker compose','Kubernetes / Helm']];
nativeTable(stack,50,128,1100,612,[220,530,350],22);footer('右列为备选；建议项与规划项不等于已经部署');

slide('F-23');
const infrastructure=[{title:'应用容器',y:143,color:C.blue,fill:C.pale,names:['api\n/api/v1','mcp\n/mcp','workers\n9 个角色','scheduler','web']},{title:'数据容器',y:359,color:C.navy,fill:'#E2EEF7',names:['postgres\npgvector','neo4j','opensearch\nIK','redis / nats','minio']},{title:'可观测容器',y:594,color:C.green,fill:C.mint,names:['langfuse','prometheus','grafana']}];
infrastructure.forEach(({title,y,color,fill,names},idx)=>{poly([[50,y],[1125,y],[1150,y+21],[75,y+21]],fill);rect(75,y+21,1075,140,fill,C.line);poly([[50,y],[75,y+21],[75,y+161],[50,y+140]],idx===2?'#BAD6A3':C.sky);text(title,86,y+34,180,82,27,color,true,'center');let cw=idx===2?237:155,gap=16;names.forEach((t,i)=>shape(t,280+i*(cw+gap),y+43,cw,91,{fill:C.white,color:idx===2?C.green:C.ink,geom:idx===1?'can':'roundRect',bold:true,size:22}));});
text('网络与消息队列',430,309,520,43,22,C.blue,false,'center');text('调用追踪 / 任务与时效指标',425,530,540,43,22,C.green,false,'center');

slide('F-24');
block('Vulnerability','漏洞事实实体',440,300,320,120,{fill:C.blue,color:C.white,size:28});
block('Advisory','公告',50,130,260,100);block('CWE','弱点分类',50,310,260,100);block('PocRef','公开 PoC 引用',50,500,260,100);
block('Component','受影响组件',890,130,260,100);shape('Version 区间 / fixed',890,251,260,60,{size:23});
block('AtlasTechnique','攻击技术',890,350,260,100,{fill:C.mint,color:C.green,size:23});
shape('Paper / Article',890,520,260,70,{fill:C.mint,color:C.green,bold:true,size:24});
shape('RiskCategory',440,505,320,60,{fill:C.yellow,color:C.gold,bold:true,size:25});shape('Regulation',440,635,320,60,{fill:C.yellow,color:C.gold,bold:true,size:25});
route([[310,180],[375,180],[375,325],[440,325]]);lineLabel('描述',329,229,92,36,23,C.blue);
route([[440,360],[310,360]]);lineLabel('弱点',329,320,92,34,23,C.blue);
route([[440,395],[375,395],[375,550],[310,550]]);lineLabel('引用',329,461,92,36,23,C.blue);
route([[760,325],[825,325],[825,180],[890,180]]);lineLabel('影响',779,229,92,36,23,C.blue);segment(1020,230,1020,251);
route([[760,360],[850,360],[850,400],[890,400]],{color:C.green,dash:'dashed'});lineLabel('映射',779,320,92,34,23,C.green);
route([[760,395],[805,395],[805,555],[890,555]],{color:C.green,dash:'dashed'});lineLabel('讨论',779,461,92,36,23,C.green);
segment(600,420,600,505,{color:C.gold,arrow:true});lineLabel('归类',549,451,102,35,23,C.gold);segment(600,565,600,635,{color:C.gold,arrow:true});lineLabel('规制',549,584,102,35,23,C.gold);
text('描述 DESCRIBES    影响 AFFECTS    弱点 HAS_CWE    映射 MAPS_TO',50,716,1100,34,23);
text('引用 HAS_POC_REF    讨论 DISCUSSED_IN    归类 IN_CATEGORY    规制 GOVERNED_BY',50,752,1100,34,23);
text('边属性：reason / confidence / method / created_by_agent',50,794,1100,36,23,C.gray);

slide('F-25');
const failure=shape('请求失败',440,124,320,67,{fill:C.pink,color:C.red,bold:true,size:28});const err=shape('错误类型',440,260,320,130,{geom:'diamond',fill:C.yellow,color:C.gold,bold:true,size:28});edge(failure,err,{from:'bottom',to:'top',color:C.red});
const retr=block('429 / 5xx / 超时','退避重试 ≤6 次',65,459,470,133,{fill:C.pale});const hard=block('4xx（非 429）','直接死信并告警',665,459,470,133,{fill:C.pink,color:C.red});route([[440,325],[300,325],[300,459]]);route([[760,325],[900,325],[900,459]],{color:C.red});
const dead=shape('DLQ / 每 15 min 重放',355,666,490,64,{geom:'can',fill:C.yellow,color:C.gold,bold:true,size:25});route([[300,592],[300,624],[600,624],[600,666]],{color:C.gold});route([[900,592],[900,624],[600,624]],{color:C.red,arrow:false});footer('Retry-After 优先；否则 1 s 起 ×2，上限 5 min，±20% 抖动；连续 3 周期失败后降级');

slide('F-26');
panel('允许提供',50,148,350,539,{fill:C.mint,color:C.green});panel('禁止提供',800,148,350,539,{fill:C.pink,color:C.red});
const allowed=['聚合计数与分布','PoC 链接与标题','修复版本与缓解'];const denied=['IP / 主机明细','利用代码','执行能力 / 主动扫描'];
allowed.forEach((t,i)=>{numbered(i+1,79,250+i*134,C.green);text(t,142,244+i*134,235,67,25,C.green,true);});
denied.forEach((t,i)=>{shape('×',827,250+i*134,44,44,{geom:'ellipse',fill:C.red,line:'none',color:C.white,bold:true,size:28});text(t,883,244+i*134,246,67,25,C.red,true);});
const service=block('只读服务层','Critic\n输出过滤',455,303,290,210,{fill:C.blue,color:C.white,size:29});segment(455,408,400,408,{arrow:true,color:C.green});segment(745,408,782,408,{color:C.red,dash:'dashed'});rect(778,380,5,56,C.red);text('多层边界执行',410,615,380,62,25,C.blue,true,'center');footer('合规限制在采集、存储、服务与校验多个边界执行');

slide('F-27');
const tx=[145,370,595,820,1055];segment(145,270,1055,270,{width:4});
const stamps=[['来源发布','source_\npublished_at'],['首次发现','first_seen_at'],['完成归一','normalized_at'],['完成富化','enriched_at'],['可查询','queryable_at']];
stamps.forEach(([t,d],i)=>{dot(tx[i],270,10);text(t,tx[i]-95,180,190,51,26,C.navy,true,'center');text(d,tx[i]-112,309,224,72,23,C.gray,false,'center');});
shape('采集时延\n首见 − 发布',70,434,276,110,{fill:C.pale,size:26,bold:true});shape('处理时延\n可查询 − 首见',385,434,745,110,{fill:C.mint,color:C.green,size:26,bold:true});
shape('端到端 = 可查询 − 发布\n目标值 ≤6 h（待测）',70,622,1060,115,{fill:C.yellow,color:C.gold,bold:true,size:29});footer('仅漏洞类首次发现；日更源单列；DEMO 不计；日期精度不足按当日零点计，保守高估');

slide('F-29');
const innovation=[['面向 AI 基础设施的垂直多源融合','P0 5 min / 无 CVE 入库','监测 / 时效'],['可解释的自动关联推理引擎','边带理由 / Critic 门槛','富化 / 准确'],['从依赖文件出发的影响自查','OSV 求解 / 三种结果','富化 / Agent'],['可解释 GraphRAG 问答','三路检索 / 逐句引用','问答 / 准确'],['内部多智能体编排与外部 MCP 开放','9 角色 / 统一服务层','Agent'],['时效可观测与故障自愈','五段时间戳 / 故障恢复','时效 / 自动化'],['开放的插件生态','8 Schema / 三类扩展点','Agent / 文档']];
text('创新方向',111,117,480,48,27,C.blue,true);text('关键机制',625,117,320,48,27,C.blue,true);text('验证维度',984,117,190,48,27,C.green,true);
innovation.forEach((r,i)=>{let y=185+i*80;rect(50,y,1100,71,i%2?C.white:C.fog);numbered(i+1,62,y+13,i%2?C.green:C.blue);text(r[0],118,y+4,488,65,24,C.ink,true);text(r[1],624,y+5,350,63,22,C.gray);text(r[2],979,y+5,170,63,22,C.green,true,'center');});footer('七项创新均需第四章评测验证；当前未测结果保持占位');

slide('F-30');
const tests=[['时效','五段时间戳','按源分项','P50 / P95','目标值 ≤6 h\n（待测）'],['富化','200 条金标','Critic 前后','准确率 / κ','目标值 ≥95%\n（待测）'],['问答','约 100 题','三组对照','答案 / 引用','目标值待定\n（待测）'],['自愈','6 个场景','故障注入','成功率 / 恢复','目标值待定\n（待测）'],['兼容','4 类客户端','远程 / stdio','加载 / 续取','目标值待定\n（待测）']];
['输入','对照 / 方法','观测指标','验收目标'].forEach((t,i)=>text(t,29,281+i*112,150,56,22,C.gray,true,'center'));
tests.forEach((r,i)=>{let x=192+i*198;ribbon(r[0],x,161,184,i%2?C.navy:C.blue);r.slice(1,4).forEach((t,j)=>{shape(t,x,267+j*112,184,85,{fill:j===2?C.mint:C.pale,color:j===2?C.green:C.ink,size:22,bold:j===2});if(j<2)segment(x+92,352+j*112,x+92,377+j*112,{color:C.line,arrow:true});});shape(r[4],x,613,184,101,{fill:C.yellow,color:C.gold,bold:true,size:22});});footer('同模型同提示；保存原始结果；未执行不计为通过');

await (await PresentationFile.exportPptx(P)).save(path.join(build,'redrawn-draft.pptx'));
await fs.writeFile(path.join(build,'slides-order.json'),JSON.stringify(order,null,2));
console.log(`Created ${P.slides.items.length} editable figure slides`);

from pathlib import Path
root=Path('D:/dianzi/output/shaowang-paper-figures-20261016/build')
s=Path('D:/dianzi/output/shaowang-figure-redesign-20261016/build/redraw.mjs').read_text(encoding='utf-8')
s=s.replace("radius=12", "radius=4")
s=s.replace(" const a=S.shapes.add", " size=Math.max(size,23);\n const a=S.shapes.add")
s=s.replace("insets:8", "insets:3")
s=s.replace("function footer(t){text(t,45,772,1110,48,18,C.gray,false,'center');}","function footer(t){text(t,45,770,1110,66,23,C.gray,false,'left');}")
s=s.replace("text(id,42,23,100,40,22,C.blue,true);text(sp.title,148,16,1000,55,32,C.ink,true);rect(48,87,1104,2,C.line);", "")
s=s.replace("text(desc,290,y+22,584,62,i===3?21:23,C.ink)","text(desc,290,y+22,584,62,23,C.ink)")
s=s.replace("'source_published_at','first_seen_at','normalized_at','enriched_at','queryable_at'", "'source_\\npublished_at','first_seen_at','normalized_at','enriched_at','queryable_at'")
s=s.replace("224,50,18", "224,72,23")
s=s.replace("['来源发布','source_published_at']", "['来源发布','source_\\npublished_at']")
a=s.index("slide('F-04');"); b=s.index("slide('F-05');")
s=s[:a]+'''slide('F-04');
const lanes=['厂商仓库','编排器','采集器','归一器','富化器','校验器','图写入器','评估器','编码智能体'];
const lx=lanes.map((_,i)=>74+i*131.5);
lanes.forEach((t,i)=>{shape(t,lx[i]-60,120,120,62,{fill:i===0||i===8?C.yellow:C.pale,size:24,bold:true});segment(lx[i],190,lx[i],666,{color:C.line,dash:'dashed',width:1.2});});
const seq=[[1,2,'定时派发'],[2,0,'增量轮询'],[0,2,'公告内容'],[2,3,'RawEvent'],[3,4,'归一结果'],[4,5,'富化产出'],[5,6,'校验通过'],[6,7,'影响评估'],[7,8,'经校验返回']];
seq.forEach(([a,b,t],i)=>{let y=230+i*52;segment(lx[a],y,lx[b],y,{arrow:true,color:i>=6?C.green:C.blue});text(t,Math.min(lx[a],lx[b])-15,y-34,Math.abs(lx[a]-lx[b])+30,32,23,C.ink,false,'center');});
text('编排器 Orchestrator    采集器 Collector    归一器 Triage',50,684,1100,34,23);
text('富化器 Enricher    校验器 Critic    图写入器 GraphWriter    评估器 Assessor',50,726,1100,34,23);
footer('演示注入 / 自有仓库 webhook 验签后触发立即 poll；DEMO 单列');

'''+s[b:]
a=s.index("slide('F-14');");b=s.index("slide('F-15');")
s=s[:a]+'''slide('F-14');
const center14=block('Vulnerability','漏洞事实',425,337,350,120,{fill:C.blue,color:C.white});
const graphNodes=[['Advisory','公告',55,130,'描述',false],['Component','组件',875,130,'影响',false],['CWE','弱点分类',55,337,'弱点',false],['AtlasTechnique','攻击技术',875,337,'映射',true],['PocRef','公开引用',55,548,'引用',false],['Paper / Article','论文与文章',875,548,'讨论',true]];
graphNodes.forEach(([t,d,x,y,rel,weak],i)=>{block(t,d,x,y,270,114,{fill:weak?C.mint:C.pale,color:weak?C.green:C.blue,size:24});let ex=x<400?325:875,sx=x<400?425:775,bx=x<400?375:825,py=i<2?360:i<4?397:434;route(i===0?[[ex,y+57],[bx,y+57],[bx,py],[sx,py]]:[[sx,py],[bx,py],[bx,y+57],[ex,y+57]],{color:weak?C.green:C.blue,dash:weak?'dashed':'solid'});lineLabel(rel,x<400?329:779,y+17,92,38,23,weak?C.green:C.blue);});
text('规则理由：aliases 含 CVE',390,140,420,46,24,C.blue,false,'center');text('弱关联：摘要相似 + 组件共现',385,205,430,68,23,C.green,false,'center');text('处置关联：修复 + 缓解模板\\n版本求解：清单 × 影响区间',380,540,440,98,24,C.ink,false,'center');
text('描述 DESCRIBES    影响 AFFECTS    弱点 HAS_CWE',50,690,1100,34,23);
text('映射 MAPS_TO    引用 HAS_POC_REF    讨论 DISCUSSED_IN',50,730,1100,34,23);
footer('实线：确定性关联；虚线：须经 Critic 校验的弱关联');

'''+s[b:]
a=s.index("slide('F-24');");b=s.index("slide('F-25');")
s=s[:a]+'''slide('F-24');
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
route([[760,360],[825,360],[825,400],[890,400]],{color:C.green,dash:'dashed'});lineLabel('映射',779,320,92,34,23,C.green);
route([[760,395],[825,395],[825,555],[890,555]],{color:C.green,dash:'dashed'});lineLabel('讨论',779,461,92,36,23,C.green);
segment(600,420,600,505,{color:C.gold,arrow:true});lineLabel('归类',549,451,102,35,23,C.gold);segment(600,565,600,635,{color:C.gold,arrow:true});lineLabel('规制',549,584,102,35,23,C.gold);
text('描述 DESCRIBES    影响 AFFECTS    弱点 HAS_CWE    映射 MAPS_TO',50,716,1100,34,23);
text('引用 HAS_POC_REF    讨论 DISCUSSED_IN    归类 IN_CATEGORY    规制 GOVERNED_BY',50,752,1100,34,23);
text('边属性：reason / confidence / method / created_by_agent',50,794,1100,36,23,C.gray);

'''+s[b:]
s=s.replace("insets:10", "insets:4")
s=s.replace("function nativeTable(values,x,y,w,h,widths,size=22){", "function nativeTable(values,x,y,w,h,widths,size=23){\n size=Math.max(size,23);")
(root/'redraw.mjs').write_text(s,encoding='utf-8')

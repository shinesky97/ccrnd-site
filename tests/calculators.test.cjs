const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(process.env.CALCULATOR_FILE || 'calculators.html','utf8');
function app(){
  const elements={};
  for(const m of html.matchAll(/<(input|select|div)[^>]*id="([^"]+)"[^>]*>/g)){
    elements[m[2]]={value:(m[0].match(/value="([^"]*)"/)||[])[1]||'',hidden:true,innerHTML:'',events:{},addEventListener(k,f){this.events[k]=f;}};
  }
  const buttons=[...html.matchAll(/data-calc="([^"]+)"/g)].map(m=>({key:m[1],getAttribute(){return this.key;},addEventListener(k,f){this[k]=f;}}));
  const document={getElementById:id=>elements[id],querySelectorAll:s=>s==='.calc-run'?buttons:[]};
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],{document});
  return (key,values)=>{for(const [id,v] of Object.entries(values))elements[id].value=String(v);buttons.find(b=>b.key===key).click();return elements['out-'+key].innerHTML;};
}
function row(output,label){const start=output.indexOf('<span>'+label+'</span><b>');assert.ok(start>=0, label);return Number(output.slice(start).match(/<b>([-\d,]+)원/)[1].replaceAll(',',''));}
function total(output){return Number(output.match(/ro-big">([-\d,]+)원/)[1].replaceAll(',',''));}
const acq=(heavy,big,kind='buy',price=1000000000)=>app()('acq',{'a-price':price,'a-kind':kind,'a-heavy':heavy,'a-area':big});
for(const [hv,big,expected] of [[0,0,33000000],[0,1,35000000],[8,0,84000000],[8,1,90000000],[12,0,124000000],[12,1,134000000]])test(`acquisition ${hv}% area ${big}`,()=>assert.equal(total(acq(hv,big)),expected));
for(const [kind,expected] of [['gift',40000000],['inherit',31600000]])test(`non-sale ignores stale heavy selection: ${kind}`,()=>assert.equal(total(acq(12,1,kind)),expected));
for(const [price,expected] of [[600000000,6000000],[750000000,15000000],[900000000,27000000]])test(`sale boundary ${price}`,()=>assert.equal(row(acq(0,0,'buy',price),'취득세'),expected));
for(const [price,ratio] of [[300000000,43],[300000001,44],[600000000,44],[600000001,45],[900000000,45],[1000000000,45]])test(`one-home ratio ${price}`,()=>{const out=app()('prop',{'p-price':price,'p-one':1,'p-ratio':60,'p-city':0});assert.equal(row(out,`과세표준 (×${ratio}%)`),Math.round(price*ratio/100));});
test('one-home 500m legal fixture',()=>{const out=app()('prop',{'p-price':500000000,'p-one':1,'p-ratio':60,'p-city':1});assert.equal(row(out,'재산세'),260000);assert.equal(total(out),620000);});
test('one-home over 900m retains 45% but standard rates',()=>{const out=app()('prop',{'p-price':1000000000,'p-one':1,'p-ratio':60,'p-city':0});assert.equal(row(out,'재산세'),1170000);});
test('general property remains 60%',()=>{const out=app()('prop',{'p-price':500000000,'p-one':0,'p-ratio':44,'p-city':0});assert.equal(row(out,'과세표준 (×60%)'),300000000);assert.equal(row(out,'재산세'),570000);});
function house(hold,live,type='one',heavy=0){return app()('house',{'h-sale':1500000000,'h-buy':900000000,'h-cost':0,'h-hold':hold,'h-live':live,'h-type':type,'h-heavy':heavy});}
for(const [hold,live,rate] of [[2,2,0],[3,2,20],[10,0,20],[3,0,6],[10,10,80],[20,0,30]])test(`LTD hold=${hold} live=${live}`,()=>assert.equal(row(house(hold,live),`장기보유특별공제(${rate}%)`),120000000*rate/100));
test('heavy house excludes LTD',()=>assert.equal(row(house(10,0,'general',20),'장기보유특별공제(0%)'),0));
test('contradictory home status blocked',()=>assert.match(house(10,2,'one',20),/동시에 선택할 수 없습니다/));
test('residency beyond ownership blocked',()=>assert.match(house(3,4),/거주기간은 보유기간을 초과/));
for(const [base,tax] of [[14000000,840000],[50000000,6240000],[88000000,15360000],[150000000,37060000],[300000000,94060000],[500000000,174060000],[1000000000,384060000],[1100000000,429060000]])test(`unchanged income bracket ${base}`,()=>assert.equal(row(app()('income',{'in-income':base}),'산출세액(국세)'),tax));
for(const [base,tax] of [[200000000,20000000],[20000000000,3980000000],[300000000000,65580000000],[400000000000,90580000000]])test(`unchanged corp bracket ${base}`,()=>assert.equal(row(app()('corp',{'in-corp':base}),'법인세(국세)'),tax));
test('do not claim full monthly verification',()=>{assert.match(html,/updated: 2026-09-24/);assert.match(html,/전체 검증 완료를 의미하지 않습니다/);});

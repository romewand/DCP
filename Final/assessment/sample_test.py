import json,re,sys
from pathlib import Path
from datetime import datetime,timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
sys.stdout.reconfigure(encoding='utf-8')
out=Path(__file__).resolve().parent;url='https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=PSCompPars'
o=webdriver.ChromeOptions();o.add_argument('--headless=new');o.add_argument('--window-size=1600,1000');o.page_load_strategy='eager'
d=webdriver.Chrome(options=o);d.set_page_load_timeout(60)
read="""return Array.from(document.querySelectorAll('table.obj > tbody > tr')).map(r=>Array.from(r.children).map(c=>({text:c.innerText.trim(),html:c.innerHTML,main:c.querySelector('.supersubNumber')?.textContent??null,upper:c.querySelector('.superscript')?.textContent??null,lower:c.querySelector('.subscript')?.textContent??null}))).filter(r=>r.length===35 && r[2].text && r[2].html.includes('/overview/'));"""
seen={};log=[]
try:
 d.get(url);wait=WebDriverWait(d,60);wait.until(lambda b:len(b.execute_script(read))>0)
 grid=d.find_element(By.CSS_SELECTOR,'div.objbox')
 for step in range(35):
  rows=d.execute_script(read)
  for row in rows: seen.setdefault(row[2]['text'],row)
  log.append({'step':step,'rendered_rows':len(rows),'unique_collected':len(seen),'first':rows[0][2]['text'],'last':rows[-1][2]['text']})
  if len(seen)>=300:break
  old=rows[-1][2]['text'];d.execute_script('arguments[0].scrollTop += 400;',grid)
  wait.until(lambda b:b.execute_script(read)[-1][2]['text']!=old)
 print('COLLECTED',len(seen),'SCROLL_STEPS',len(log)-1)
 d.save_screenshot(str(out/'scrolled_table.png'))
 out.joinpath('selenium_raw_sample.json').write_text(json.dumps({'url':url,'collected_at_utc':datetime.now(timezone.utc).isoformat(),'method':'Selenium rendered DOM extraction with scrolling; no direct data API requests','rows':list(seen.values()),'scroll_log':log},ensure_ascii=False,indent=2),encoding='utf-8')
 fields={'planet_name':2,'host_name':3,'number_of_stars':4,'number_of_planets':5,'discovery_method':6,'discovery_year':7,'discovery_facility':8,'controversial_flag':9,'orbital_period_days':10,'semi_major_axis_au':11,'radius_earth':12,'mass_earth':14,'mass_provenance':16,'eccentricity':17,'equilibrium_temp_k':19,'stellar_teff_k':22,'distance_pc':30}
 clean=[];invalid=[]
 for name,row in seen.items():
  r={k:' '.join(row[i]['text'].split()) for k,i in fields.items()}
  try:
   for k in ['number_of_stars','number_of_planets','discovery_year','controversial_flag']:r[k]=int(r[k])
   assert r['planet_name'] and r['host_name'] and r['discovery_method']
   for k in ['orbital_period_days','semi_major_axis_au','radius_earth','mass_earth','eccentricity','equilibrium_temp_k','stellar_teff_k','distance_pc']:
    raw=row[fields[k]];r[k+'_raw']=raw['text'];r[k+'_limit']=raw['text'][:1] if raw['text'].startswith(('<','>')) else None
    v=raw['main'] or raw['text'];match=re.match(r'^\s*[<>]?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)',v)
    r[k]=float(match.group(1)) if match else None
   clean.append(r)
  except (ValueError,AssertionError):invalid.append(name)
 profile={'raw_unique':len(seen),'cleaned':len(clean),'invalid_core_rows':invalid,'missing':{k:sum(x[k] is None or x[k]=='' for x in clean) for k in fields},'discovery_methods':sorted({r['discovery_method'] for r in clean}),'discovery_year_range':[min(r['discovery_year'] for r in clean),max(r['discovery_year'] for r in clean)],'mass_provenance':sorted({r['mass_provenance'] for r in clean}),'limit_cells':sum(r.get(k+'_limit') is not None for r in clean for k in fields),'scope':'Alphabetical prefix feasibility sample, not representative or complete catalogue'}
 for n,v in [('cleaned_sample.json',clean),('sample_profile.json',profile)]:out.joinpath(n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(profile,indent=2));print('FOOTER',d.find_element(By.TAG_NAME,'body').text[-250:])
finally:d.quit()
# A separate browser run disables JavaScript; no API or bulk download is used.
o2=webdriver.ChromeOptions();o2.add_argument('--headless=new');o2.add_experimental_option('prefs',{'profile.managed_default_content_settings.javascript':2});o2.page_load_strategy='eager'
b=webdriver.Chrome(options=o2)
try:
 b.get(url);disabled={'rendered_planet_links':len(b.find_elements(By.CSS_SELECTOR,'table.obj a[href*="/overview/"]')),'title':b.title};out.joinpath('javascript_disabled.json').write_text(json.dumps(disabled),encoding='utf-8');print('JS_DISABLED',disabled)
finally:b.quit()

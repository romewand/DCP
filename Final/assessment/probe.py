import json,time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
p=Path(__file__).resolve().parent
o=webdriver.ChromeOptions();o.add_argument('--headless=new');o.add_argument('--window-size=1600,1000')
d=webdriver.Chrome(options=o)
try:
 d.get('https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=PSCompPars')
 WebDriverWait(d,60).until(lambda x: 'Orbital Period' in x.find_element(By.TAG_NAME,'body').text)
 time.sleep(3)
 p.joinpath('rendered.html').write_text(d.page_source,encoding='utf-8');p.joinpath('visible.txt').write_text(d.find_element(By.TAG_NAME,'body').text,encoding='utf-8');d.save_screenshot(str(p/'table.png'))
 print(d.title);print(d.find_element(By.TAG_NAME,'body').text[:16000]);print('TABLES',[(e.get_attribute('id'),e.get_attribute('class'),len(e.find_elements(By.TAG_NAME,'tr'))) for e in d.find_elements(By.TAG_NAME,'table')]);print('INPUTS',[(e.get_attribute('id'),e.get_attribute('type'),e.get_attribute('value')) for e in d.find_elements(By.TAG_NAME,'input')][:50])
finally:d.quit()

"""Browser regression checks for the static preview; Python + Playwright Chromium."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--base',default='')
parser.add_argument('--skip-layout',action='store_true')
parser.add_argument('--output',type=Path,default=Path('/tmp/abd-preview-checks'))
a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
site='index.html' if (a.root/'index.html').exists() else 'прототип_сайта.html'
view='3d.html' if (a.root/'3d.html').exists() else '3d_портфолио.html'
base=a.base.rstrip('/')+'/' if a.base else a.root.resolve().as_uri()+'/'
errors=[];checks=[]

def check(ok,label):
 if not ok:raise AssertionError(label)
 checks.append(label)

def body_width(page):
 return page.evaluate('({inner:innerWidth,body:document.documentElement.scrollWidth})')

def goto(page,path='/'):
 if page.locator('#qx').count():page.locator('#qx').click()
 page.goto(base+site+'#'+path);page.wait_for_load_state('networkidle')

def choose(page,key,value):
 page.locator(f'[data-k="{key}"][data-v="{value}"]').click()

def flow(page,area=120,need='both',extras=False,sup='none',sections=None):
 goto(page,'/privatehouse')
 page.locator('[data-start="только идея"]').first.click()
 page.locator('#resetDraft').click()
 choose(page,'have','есть участок');page.locator('#qn').click()
 page.locator('#ar').fill(str(area));page.locator('#qn').click()
 choose(page,'need',need)
 for section in sections or []:page.locator(f'[data-section="{section}"]').click()
 page.locator('#qn').click();choose(page,'floors','1')
 if extras:
  for x in ['garage','banya','naves','cokol']:page.locator(f'[data-ex="{x}"]').click()
 choose(page,'supervision',sup)
 if sup!='none':page.locator('#supQty').fill('2')
 page.locator('#qn').click();page.locator('#region').fill('Пермь');choose(page,'when','3 мес');page.locator('#qn').click()
 return page.locator('.quote-head h3').inner_text().replace('\xa0',' ')

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 ctx=browser.new_context(viewport={'width':1440,'height':960},accept_downloads=True)
 page=ctx.new_page();page.on('pageerror',lambda e: errors.append(str(e)))
 goto(page,'/map')
 routes=page.locator('.map a').evaluate_all('(els)=>els.map(e=>e.getAttribute("href").slice(1))')
 check(len(routes)>=45,'Route map contains all public pages')
 for width in ([] if a.skip_layout else [320,390,768,1440]):
  page.set_viewport_size({'width':width,'height':900})
  for route in routes:
   goto(page,route)
   check(page.locator('#page h1').count()==1,f'{width}px {route}: one H1')
   size=body_width(page);check(size['body']<=size['inner']+1,f'{width}px {route}: no horizontal overflow {size}')
   check(page.locator('img').evaluate_all('async xs=>{for(const i of xs)i.loading="eager";return (await Promise.all(xs.map(i=>i.decode().then(()=>i.naturalWidth>0).catch(()=>false)))).every(Boolean)}'),f'{width}px {route}: images load')
  goto(page,'/');page.screenshot(path=str(a.output/f'home-{width}.png'))
 page.set_viewport_size({'width':1440,'height':960})
 for area,need,expected in [(30,'both',125000),(50,'both',125000),(120,'both',300000),(200,'pp',50000),(201,'pp',50000),(209,'pp',50000),(210,'pp',100000),(300,'pp',100000),(301,'pp',150000),(301,'rd',752500)]:
  result=flow(page,area,need)
  check(str(expected)==''.join(c for c in result if c.isdigit()),f'Pricing {area}m² {need}: {expected}')
 check('300000'==''.join(c for c in flow(page,120,'both',True) if c.isdigit()),'Outbuildings never silently add area')
 check('310000'==''.join(c for c in flow(page,120,'both',sup='visit') if c.isdigit()),'Two supervision visits explicitly add 10,000')
 check('400000'==''.join(c for c in flow(page,120,'both',sup='month') if c.isdigit()),'Two supervision months explicitly add 100,000')
 check('78000'==''.join(c for c in flow(page,120,'sections',sections=['ir','sm']) if c.isdigit()),'Selected sections IR + SM cost 78,000')
 check('Подберём' in flow(page,120,'idk'),'Unknown composition never invents a package total')
 flow(page,120,'both');page.screenshot(path=str(a.output/'quote-desktop.png'))
 check('250000' in ''.join(page.locator('#ov .flag').first.inner_text().split()),'PP is deducted: RD remainder 250,000')
 with page.expect_download() as dl:page.locator('#saveQuote').click()
 check('300' in Path(dl.value.path()).read_text(),'Calculation download is a real readable file')
 page.locator('#editQuote').click();check(page.locator('[data-v="both"]').get_attribute('aria-pressed')=='true','Editing retains composition')
 page.locator('#qb').click();check(page.locator('#ar').input_value()=='120','Editing retains area')
 page.locator('#ar').fill('0');check(page.locator('#qn').is_disabled(),'Zero area is rejected')
 page.locator('#ar').fill('10001');check(page.locator('#qn').is_disabled(),'Excessive area is rejected')
 page.locator('#ar').fill('155');page.locator('#qx').click();page.reload();page.locator('[data-start="только идея"]').first.click();page.locator('#qn').click();check(page.locator('#ar').input_value()=='155','Draft survives reload')
 page.keyboard.press('Escape');check(page.locator('.ov').count()==0,'Escape closes modal')
 goto(page,'/privatehouse/services/estimate');page.locator('[data-start]').first.click();page.locator('#qn').click();check(page.locator('[data-section="sm"]').get_attribute('aria-pressed')=='true','Estimate service enters the SM calculator')
 page.locator('#qx').click()
 goto(page,'/privatehouse/portfolio');page.locator('[data-filter="до 100 м²"]').click();check(page.locator('#portfolioCards .card').count()==3,'Portfolio small-area filter returns three houses');page.locator('[data-filter="свыше 200 м²"]').click();check(page.locator('#portfolioCards .card').count()==1,'Portfolio large-area filter returns villa')
 goto(page,'/start/bath48');page.locator('[data-v="есть участок"]').click();page.locator('#qn').click();check(page.locator('#ar').input_value()=='48','3D-to-quiz deep link transfers actual model area');page.locator('#qx').click()
 flow(page,120,'both');page.locator('#ql').click();check('120 м²' in page.locator('.brief-summary').inner_text(),'Questionnaire receives price and area');page.locator('[name="life"]').fill('Семья и кабинет');page.locator('#briefForm button[type="submit"]').click();page.locator('#contactForm button[type="submit"]').click();check(page.locator('#contactError').inner_text()!='','Empty contact form is blocked');page.locator('#nm').fill('Тест');page.locator('#ct').fill('invalid');page.locator('#ag').check();page.locator('#sendConsent').check();page.locator('#contactForm button[type="submit"]').click();check('корректный' in page.locator('#contactError').inner_text(),'Malformed contact is blocked');page.locator('#ct').fill('demo@example.com');page.locator('#contactForm button[type="submit"]').click();check('не отправлена' in page.locator('.hint').inner_text(),'Completion truthfully says request has not been sent')
 with page.expect_download() as dl:page.locator('#downloadRequest').click()
 request=Path(dl.value.path()).read_text();check('Семья и кабинет' in request and 'demo@example.com' in request,'Request download includes brief and contact')
 page.locator('#qx').click();goto(page,'/zayavka/supplier');page.locator('#roleField0').fill('Тестовая компания');page.locator('[data-role-next]').click();page.locator('#nm').fill('Поставщик');page.locator('#ct').fill('supplier@example.com');page.locator('#ag').check();page.locator('#sendConsent').check();page.locator('#contactForm button[type="submit"]').click()
 with page.expect_download() as dl:page.locator('#downloadRequest').click()
 request=Path(dl.value.path()).read_text();check('Тестовая компания' in request and 'Семья и кабинет' not in request and 'Итого:' not in request,'Supplier is isolated from prior client quote and brief')
 page.locator('#qx').click();goto(page,'/calcalfa');page.locator('#buildArea').fill('250');page.locator('#buildForm button[type="submit"]').click();check('250' in page.locator('#message').input_value(),'Construction parameters transfer into own request');page.locator('#qx').click()
 goto(page,'/opros');check('120 м²' in page.locator('.brief-summary').inner_text(),'Construction form does not change design area')
 goto(page,'/bad-route');check('адрес изменился' in page.locator('h1').inner_text(),'Unknown route shows real not-found page')
 goto(page,'/privatehouse/services/not-real');check('адрес изменился' in page.locator('h1').inner_text(),'Unknown service does not fall back to unrelated service')
 page.set_viewport_size({'width':390,'height':844});goto(page);page.locator('#menuToggle').click();check(page.locator('nav.main').is_visible(),'Mobile navigation opens');page.locator('nav.main a').first.click();check(page.locator('#menuToggle').get_attribute('aria-expanded')=='false','Mobile menu closes on navigation')
 flow(page,209,'both',True);page.screenshot(path=str(a.output/'quote-mobile.png'));check(body_width(page)['body']<=390,'Mobile quote does not overflow')
 page.locator('#qf').click();page.locator('#qx').focus();page.keyboard.press('Tab');check(page.evaluate('document.activeElement.closest("#ov")!==null'),'Tab stays within contact dialog');page.keyboard.press('Escape')
 for width,height in [(390,844),(768,900),(1440,960),(1366,650)]:
  page.set_viewport_size({'width':width,'height':height});page.goto(base+view+'#as80');page.wait_for_load_state('networkidle');page.wait_for_timeout(700)
  check(page.evaluate('!!document.querySelector("#cv").getContext("webgl")'),'WebGL initializes')
  check(body_width(page)['body']<=width+1,f'3D {width}px: no horizontal overflow')
  for id in ['as80','as130','kr90','vila220','bath48']:
   page.locator(f'#rail button').nth(['as80','as130','kr90','vila220','bath48'].index(id)).click();page.wait_for_timeout(250)
   check(page.locator('#quoteCTA').get_attribute('href').endswith('/start/'+id),f'3D {width}px {id}: correct quiz link')
  page.locator('#bEx').click();check(page.locator('.layer-panel').is_visible(),f'3D {width}px: layer explanation visible');page.locator('#bEx').click();check(page.locator('#bEx').get_attribute('aria-pressed')=='false','Assembly toggles back');page.locator('#bTop').click();page.locator('#zoomIn').click();page.locator('#zoomOut').click();page.locator('#bRot').click();check(page.locator('#bRot').get_attribute('aria-pressed')=='true','Rotation can be enabled');page.locator('#bRes').click();page.wait_for_timeout(500);page.screenshot(path=str(a.output/f'3d-{width}.png'),full_page=width<800)
 check(not errors,'No uncaught browser errors: '+str(errors))
 browser.close()
(a.output/'results.json').write_text(json.dumps({'routes':len(routes),'passed':len(checks),'checks':checks,'errors':errors},ensure_ascii=False,indent=2))
print(json.dumps({'routes':len(routes),'passed':len(checks),'errors':errors,'screenshots':str(a.output)},ensure_ascii=False))

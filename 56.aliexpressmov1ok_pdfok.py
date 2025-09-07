import time
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import base64
import argparse
#mov3_10

# 전역 설정: '더보기' 최대 클릭 횟수 제한
MAX_SHOW_MORE_CLICKS = 2
SHOW_MORE_CLICKS = 0

# CLI arguments
parser = argparse.ArgumentParser(description="AliExpress product scraper/downloader")
parser.add_argument("--url", dest="url", default="", help="Product URL to fetch")
parser.add_argument("--out_dir", dest="out_dir", default="", help="Base download directory")
parser.add_argument("--headless", dest="headless", action="store_true", help="Run Chrome headless")
parser.add_argument("--max_show_more", dest="max_show_more", type=int, default=2, help="Max 'show more' clicks")
args, unknown = parser.parse_known_args()

# Apply CLI overrides
if isinstance(args.max_show_more, int) and args.max_show_more >= 0:
    MAX_SHOW_MORE_CLICKS = args.max_show_more
def save_product_details(driver, folder_path):
    """상품 상세 정보 저장"""
    print("상품 상세 정보 추출 중...")
    
    # 상품 정보 추출
    product_info = {
        "기본정보": {},
        "상세설명": "",
        "스펙정보": {},
        "구매정보": {},
        "배송정보": {},
        "판매자정보": {},
        "리뷰정보": {}
    }
    
    try:
        # PDF 생성을 위한 스타일 추가
        print("PDF 생성을 위한 스타일 추가 중...")
        driver.execute_script("""
            var style = document.createElement('style');
            style.type = 'text/css';
            style.innerHTML = `
                @media print {
                    body { margin: 0; padding: 0; }
                    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                    img { max-width: 100% !important; height: auto !important; }
                    video { display: none !important; }
                    button, .header, .footer, nav, iframe { display: none !important; }
                    .product-description, .detail-desc-decorate { display: block !important; }
                }
            `;
            document.head.appendChild(style);
        """)
        
        # 전체 페이지 PDF 저장
        try:
            print("전체 페이지 PDF 저장 중...")
            # 페이지 준비
            driver.execute_script("""
                // 불필요한 요소 숨기기
                document.querySelectorAll('iframe, video, button').forEach(el => el.style.display = 'none');
                // 이미지 최적화
                document.querySelectorAll('img').forEach(img => {
                    if (img.src && !img.src.startsWith('data:')) {
                        img.style.maxWidth = '100%';
                        img.style.height = 'auto';
                    }
                });
            """)
            
            # 전체 높이 설정
            total_height = driver.execute_script("""
                return Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight,
                    document.body.offsetHeight,
                    document.documentElement.offsetHeight
                );
            """)
            
            # 윈도우 크기 설정
            driver.set_window_size(1200, total_height)
            time.sleep(2)  # 렌더링 대기
            
            # PDF 인쇄 설정
            pdf_params = {
                "landscape": False,
                "displayHeaderFooter": False,
                "printBackground": True,
                "preferCSSPageSize": True,
                "paperWidth": 8.27,  # A4
                "paperHeight": 11.69,
                "marginTop": 0.4,
                "marginBottom": 0.4,
                "marginLeft": 0.4,
                "marginRight": 0.4,
                "scale": 0.9,
                "pageRanges": "1-"
            }
            
            # PDF로 저장
            pdf_path = os.path.join(folder_path, "product_full_page.pdf")
            pdf_data = driver.execute_cdp_cmd("Page.printToPDF", pdf_params)
            
            if pdf_data and "data" in pdf_data:
                try:
                    pdf_bytes = base64.b64decode(pdf_data["data"].encode('utf-8'))
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
                    print(f"전체 페이지 PDF 저장됨: {pdf_path}")
                except Exception as e:
                    print(f"PDF 저장 중 오류: {str(e)}")
            else:
                print("PDF 데이터를 받아오지 못했습니다.")
            
        except Exception as e:
            print(f"전체 페이지 PDF 저장 실패: {e}")
            
        # Description 섹션 PDF 저장
        try:
            print("Description 섹션 PDF 저장 중...")
            desc_selectors = [
                "//div[contains(@class, 'detail-desc-decorate')]",
                "//div[contains(@class, 'product-description')]",
                "//div[contains(@class, 'description')]"
            ]
            
            for selector in desc_selectors:
                try:
                    desc_section = driver.find_element(By.XPATH, selector)
                    if desc_section:
                        # 섹션으로 스크롤
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", desc_section)
                        time.sleep(2)
                        
                        # Description 섹션 준비
                        driver.execute_script("""
                            arguments[0].querySelectorAll('iframe, video, button').forEach(el => el.style.display = 'none');
                            arguments[0].querySelectorAll('img').forEach(img => {
                                if (img.src && !img.src.startsWith('data:')) {
                                    img.style.maxWidth = '100%';
                                    img.style.height = 'auto';
                                }
                            });
                        """, desc_section)
                        
                        # Description 섹션의 크기 가져오기
                        section_rect = driver.execute_script("""
                            const rect = arguments[0].getBoundingClientRect();
                            return {
                                x: rect.left,
                                y: rect.top + window.pageYOffset,
                                width: rect.width,
                                height: rect.height
                            };
                        """, desc_section)
                        
                        # PDF 설정
                        pdf_params = {
                            "landscape": False,
                            "displayHeaderFooter": False,
                            "printBackground": True,
                            "preferCSSPageSize": True,
                            "paperWidth": 8.27,  # A4
                            "paperHeight": 11.69,
                            "marginTop": 0.4,
                            "marginBottom": 0.4,
                            "marginLeft": 0.4,
                            "marginRight": 0.4,
                            "scale": 0.9,
                            "pageRanges": "1-",
                            "clip": section_rect
                        }
                        
                        # Description 섹션만 PDF로 저장
                        pdf_path = os.path.join(folder_path, "product_description.pdf")
                        pdf_data = driver.execute_cdp_cmd("Page.printToPDF", pdf_params)
                        
                        if pdf_data and "data" in pdf_data:
                            try:
                                pdf_bytes = base64.b64decode(pdf_data["data"].encode('utf-8'))
                                with open(pdf_path, "wb") as f:
                                    f.write(pdf_bytes)
                                print(f"Description 섹션 PDF 저장됨: {pdf_path}")
                            except Exception as e:
                                print(f"PDF 저장 중 오류: {str(e)}")
                        else:
                            print("Description PDF 데이터를 받아오지 못했습니다.")
                        break
                except Exception as section_e:
                    print(f"Description 섹션 PDF 저장 중 오류: {section_e}")
                    continue
                    
        except Exception as e:
            print(f"Description 섹션 PDF 저장 실패: {e}")
            
        # 백업으로 스크린샷도 저장
        try:
            print("스크린샷 저장 중...")
            driver.save_screenshot(os.path.join(folder_path, "product_page.png"))
            print("스크린샷 저장됨")
        except Exception as e:
            print(f"스크린샷 저장 실패: {e}")
        
        # 특정 XPath 경로의 제품 정보 추출
        try:
            print("특정 경로의 제품 정보 추출 중...")
            # 여러 가능한 선택자 시도
            selectors = [
                "//div[contains(@class, 'product-description')]",
                "//div[contains(@class, 'detail-desc-decorate')]",
                "//div[contains(@class, 'product-detail')]",
                "//div[contains(@class, 'detail-content')]",
                "//*[contains(text(), 'Product Details') or contains(text(), '상품 상세정보')]/.."
            ]
            
            section_found = False
            for selector in selectors:
                try:
                    specific_section = driver.find_element(By.XPATH, selector)
                    if specific_section:
                        section_found = True
                        # 섹션으로 스크롤
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", specific_section)
                        time.sleep(3)
                        
                        # 더보기 버튼 클릭 시도
                        click_show_more_buttons(driver)
                        
                        # 텍스트 내용 저장
                        section_text = specific_section.text.strip()
                        if section_text:
                            product_info["기본정보"]["제품상세정보"] = section_text
                            
                            # 텍스트 파일로도 저장
                            with open(os.path.join(folder_path, "product_specific_info.txt"), "w", encoding="utf-8") as f:
                                f.write(section_text)
                        break
                except:
                    continue
            
            if not section_found:
                print("제품 정보 섹션을 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"특정 경로의 제품 정보 추출 실패: {e}")
        
        # 스펙 정보 추출 (Specifications 섹션)
        try:
            print("스펙 정보 추출 중...")
            # 여러 가능한 선택자 시도
            spec_selectors = [
                "//*[contains(text(), 'Specifications')]",
                "//*[contains(text(), 'Specification')]",
                "//*[contains(text(), '제품 스펙')]",
                "//*[contains(text(), '상품 스펙')]",
                "//div[contains(@class, 'specification')]",
                "//div[contains(@class, 'product-specs')]"
            ]
            
            for selector in spec_selectors:
                try:
                    spec_section = driver.find_element(By.XPATH, selector)
                    if spec_section:
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", spec_section)
                        time.sleep(3)
                        
                        # 더보기 버튼 클릭 시도
                        click_show_more_buttons(driver)
                        
                        # 스펙 테이블 또는 리스트 찾기
                        spec_items = driver.find_elements(By.CSS_SELECTOR, 
                            "[class*='specification'] tr, [class*='spec'] li, [class*='specification-table'] tr, [class*='product-props'] li")
                        
                        for item in spec_items:
                            try:
                                text = item.text.strip()
                                if ":" in text:
                                    key, value = text.split(":", 1)
                                    if key and value:
                                        product_info["스펙정보"][key.strip()] = value.strip()
                            except:
                                continue
                        break
                except:
                    continue
            
        except Exception as e:
            print(f"스펙 정보 추출 실패: {e}")

        # Description 섹션 처리
        try:
            print("Description 섹션 처리 중...")
            # 여러 가능한 선택자 시도
            desc_selectors = [
                "//*[contains(text(), 'Description')]",
                "//*[contains(text(), '상품 설명')]",
                "//div[contains(@class, 'detail-desc')]",
                "//div[contains(@class, 'product-description')]",
                "//div[contains(@class, 'description')]"
            ]
            
            for selector in desc_selectors:
                try:
                    desc_section = driver.find_element(By.XPATH, selector)
                    if desc_section:
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", desc_section)
                        time.sleep(3)
                        
                        # 더보기 버튼 클릭 시도
                        click_show_more_buttons(driver)
                        
                        # Description 컨테이너 찾기 (부모 요소까지 포함)
                        desc_container = desc_section.find_element(By.XPATH, "./ancestor::div[contains(@class, 'description') or contains(@class, 'detail-desc')][1]")
                        
                        # Description 텍스트 저장
                        desc_text = desc_container.text.strip()
                        if desc_text:
                            product_info["상세설명"] = desc_text
                            # Description 텍스트 파일로 저장
                            with open(os.path.join(folder_path, "description_text.txt"), "w", encoding="utf-8") as f:
                                f.write(desc_text)
                        break
                except:
                    continue
            
        except Exception as e:
            print(f"Description 섹션 처리 실패: {e}")

        # 기본 정보 추출
        try:
            price_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='product-price'], [class*='uniform-banner-box-price']")
            prices = [elem.text for elem in price_elements if elem.text.strip()]
            if prices:
                product_info["기본정보"]["가격"] = prices
        except Exception as e:
            print(f"가격 정보 추출 실패: {e}")

        # 상품 속성 정보 추출
        try:
            properties = driver.find_elements(By.CSS_SELECTOR, "[class*='product-prop'], [class*='specification'], [class*='product-info']")
            for prop in properties:
                try:
                    label = prop.find_element(By.CSS_SELECTOR, "[class*='title'], [class*='key']").text
                    value = prop.find_element(By.CSS_SELECTOR, "[class*='value'], [class*='val']").text
                    if label and value:
                        product_info["기본정보"][label.strip()] = value.strip()
                except:
                    continue
        except Exception as e:
            print(f"속성 정보 추출 실패: {e}")

        # 구매 옵션 정보 추출
        try:
            options = driver.find_elements(By.CSS_SELECTOR, "[class*='sku-property'], [class*='product-options']")
            for option in options:
                try:
                    option_name = option.find_element(By.CSS_SELECTOR, "[class*='sku-title'], [class*='name']").text
                    option_values = [val.text for val in option.find_elements(By.CSS_SELECTOR, "[class*='sku-value'], [class*='value']")]
                    if option_name and option_values:
                        product_info["구매정보"][option_name.strip()] = [v.strip() for v in option_values if v.strip()]
                except:
                    continue
        except Exception as e:
            print(f"구매 옵션 추출 실패: {e}")

        # 배송 정보 추출
        try:
            shipping_elements = driver.find_elements(By.CSS_SELECTOR, 
                "[class*='product-shipping'], [class*='delivery'], [class*='shipping']")
            shipping_info = []
            
            for elem in shipping_elements:
                info = elem.text.strip()
                if info:
                    shipping_info.append(info)
            
            if shipping_info:
                product_info["배송정보"] = shipping_info
        except Exception as e:
            print(f"배송 정보 추출 실패: {e}")

        # 판매자 정보 추출
        try:
            seller_elements = driver.find_elements(By.CSS_SELECTOR, 
                "[class*='store-info'], [class*='seller-info'], [class*='store-name']")
            seller_info = []
            
            for elem in seller_elements:
                info = elem.text.strip()
                if info:
                    seller_info.append(info)
            
            if seller_info:
                product_info["판매자정보"] = seller_info
        except Exception as e:
            print(f"판매자 정보 추출 실패: {e}")

        # 리뷰 정보 추출
        try:
            review_elements = driver.find_elements(By.CSS_SELECTOR, 
                "[class*='review-item'], [class*='feedback-item']")
            reviews = []
            
            for elem in review_elements[:10]:  # 최대 10개의 리뷰만 저장
                try:
                    review_text = elem.text.strip()
                    if review_text:
                        reviews.append(review_text)
                        
                        # 리뷰 이미지가 있다면 다운로드
                        review_images = elem.find_elements(By.TAG_NAME, "img")
                        for i, img in enumerate(review_images):
                            img_url = img.get_attribute("src")
                            if img_url and not img_url.startswith("data:"):
                                download_file(img_url, folder_path, f"review_{len(reviews)}_image_{i+1}.jpg")
                except:
                    continue
            
            if reviews:
                product_info["리뷰정보"]["리뷰"] = reviews
        except Exception as e:
            print(f"리뷰 정보 추출 실패: {e}")

    except Exception as e:
        print(f"상세 정보 추출 중 오류 발생: {e}")
    
    # JSON 파일로 저장
    json_path = os.path.join(folder_path, "product_details.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(product_info, f, ensure_ascii=False, indent=2)
    print(f"상품 상세 정보 JSON 저장됨: {json_path}")
    
    return product_info

def download_file(url, folder_path, filename):
    """파일 다운로드 함수"""
    if not url or not url.startswith(('http://', 'https://')):
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.aliexpress.com/'
        }
        
        # 타임아웃 설정은 옵션으로 처리 (오류 방지)
        try:
            response = requests.get(url, stream=True, headers=headers, timeout=(5, 15))
        except:
            # 타임아웃 실패 시 타임아웃 없이 재시도
            response = requests.get(url, stream=True, headers=headers)
        
        if response.status_code == 200:
            file_path = os.path.join(folder_path, filename)
            
            # 파일 크기 확인은 옵션 처리 (비디오는 크기가 클 수 있음)
            content_length = int(response.headers.get('content-length', 0))
            if content_length > 50 * 1024 * 1024 and not filename.endswith('.mp4'):  # 50MB 이상이고 비디오가 아니면
                print(f"파일이 너무 큽니다 (크기: {content_length/1024/1024:.2f}MB): {filename}")
                return None
            
            # 청크 단위로 파일 저장
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"파일 다운로드 성공: {filename}")
            return file_path
        else:
            print(f"다운로드 실패 - 상태 코드: {response.status_code}")
    except requests.Timeout:
        print(f"다운로드 타임아웃: {filename}")
    except requests.RequestException as e:
        print(f"다운로드 중 오류 발생: {e}")
    except Exception as e:
        print(f"파일 저장 중 오류 발생: {e}")
    return None

def create_download_folder(base_folder, product_title):
    """상품별 다운로드 폴더 생성"""
    safe_title = "".join(c for c in product_title if c.isalnum() or c in (' ', '-', '_')).strip()
    folder_path = os.path.join(base_folder, safe_title[:50])
    os.makedirs(folder_path, exist_ok=True)
    print(f"폴더 생성됨: {folder_path}")
    return folder_path

def remove_image_verify_popup(driver):
    """이미지 검사 팝업 제거"""
    try:
        # 이미지 검사 팝업 닫기 버튼 찾기 시도
        close_buttons = driver.find_elements(By.CSS_SELECTOR, 
            "[class*='close'], [class*='btn-close'], [class*='close-btn'], [aria-label*='close']")
        for button in close_buttons:
            if button.is_displayed():
                try:
                    driver.execute_script("arguments[0].click();", button)
                    print("이미지 검사 팝업 닫기 성공")
                    time.sleep(1)
                    return True
                except:
                    continue
        
        # 팝업 오버레이 제거 시도
        driver.execute_script("""
            const overlays = document.querySelectorAll('[class*="verify"], [class*="popup"], [class*="modal"]');
            overlays.forEach(overlay => {
                if (overlay.style.display !== 'none') {
                    overlay.remove();
                }
            });
        """)
        
    except Exception as e:
        print(f"팝업 제거 중 오류 발생: {e}")
    return False

def click_show_more_buttons(driver):
    """'더보기' 버튼을 찾아서 클릭"""
    try:
        # 전역 클릭 제한 확인
        global SHOW_MORE_CLICKS
        if SHOW_MORE_CLICKS >= MAX_SHOW_MORE_CLICKS:
            print(f"'더보기' 최대 클릭 횟수 도달: {MAX_SHOW_MORE_CLICKS}")
            return False

        # 이미지 검사 팝업 제거
        remove_image_verify_popup(driver)
        
        # 현재 페이지의 HTML 분석
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # "더보기" 관련 텍스트를 포함하는 요소들 찾기
        more_texts = ['더보기', 'More', 'Show More', '더 보기', 'View More', 'See More']
        
        # 버튼 찾기 시도
        for text in more_texts:
            # 텍스트 내용으로 검색
            elements = soup.find_all(string=lambda s: s and text.lower() in s.lower())
            
            for element in elements:
                try:
                    # 부모 요소들 중에서 클릭 가능한 요소 찾기
                    parent = element.parent
                    for _ in range(5):  # 최대 5단계 상위까지 검색
                        if parent.name in ['button', 'a', 'div', 'span']:
                            # XPath 생성
                            components = []
                            current = parent
                            for _ in range(10):  # 최대 10단계까지의 경로 생성
                                if not current or current.name == '[document]':
                                    break
                                if 'class' in current.attrs:
                                    class_names = ' and '.join([f"contains(@class, '{c}')" for c in current['class']])
                                    components.append(f"//{current.name}[{class_names}]")
                                else:
                                    components.append(f"//{current.name}")
                                current = current.parent
                            
                            xpath = ''.join(reversed(components))
                            
                            try:
                                # XPath로 요소 찾기
                                button = driver.find_element(By.XPATH, xpath)
                                if button.is_displayed():
                                    print(f"'더보기' 버튼 발견: {text}")
                                    
                                    # 버튼이 클릭 가능한 위치로 스크롤
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                    time.sleep(2)
                                    
                                    # 이미지 검사 팝업 다시 한번 체크
                                    remove_image_verify_popup(driver)
                                    
                                    # 버튼 클릭 시도
                                    try:
                                        button.click()
                                    except:
                                        driver.execute_script("arguments[0].click();", button)

                                    # 클릭 카운트 증가 및 로그
                                    SHOW_MORE_CLICKS += 1
                                    print(f"'더보기' 버튼 클릭됨: {text} (총 {SHOW_MORE_CLICKS}/{MAX_SHOW_MORE_CLICKS})")
                                    time.sleep(3)  # 콘텐츠 로딩 대기
                                    return True
                            except:
                                continue
                            
                        parent = parent.parent
                        if not parent:
                            break
                except:
                    continue
        
        print("클릭 가능한 '더보기' 버튼을 찾지 못함")
        return False
            
    except Exception as e:
        print(f"'더보기' 버튼 처리 중 오류 발생: {e}")
        return False

# 기본 다운로드 폴더 생성 (CLI로 override 가능)
base_download_folder = args.out_dir.strip() or os.path.join(os.getcwd(), "aliexpress_downloads")
os.makedirs(base_download_folder, exist_ok=True)
print(f"기본 다운로드 폴더: {base_download_folder}")

# Chrome 옵션 설정
chrome_options = Options()
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_argument('--start-maximized')
chrome_options.add_argument('--disable-infobars')
chrome_options.add_argument('--disable-extensions')
chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
chrome_options.add_argument('--disable-notifications')
chrome_options.add_argument('--disable-popup-blocking')
chrome_options.add_argument('--disable-web-security')
if args.headless:
    try:
        chrome_options.add_argument('--headless=new')
    except Exception:
        chrome_options.add_argument('--headless')

# ChromeDriver 초기화
driver = webdriver.Chrome(options=chrome_options)
driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

try:
    # AliExpress 페이지로 이동
    search_url = (args.url.strip() or "https://www.aliexpress.com/item/3256807976992876.html")
    print(f"페이지 로딩 중: {search_url}")
    driver.get(search_url)
    
    # 페이지가 완전히 로드될 때까지 대기 (시간 증가)
    wait = WebDriverWait(driver, 60)  # 60초로 증가
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    # 초기 로딩 대기
    time.sleep(10)  # 초기 대기 시간 증가
    
    # 초기 이미지 검사 팝업 제거
    remove_image_verify_popup(driver)
    
    # 스크롤 다운하여 동적 콘텐츠 로드 (더 천천히, 더 많은 대기)
    print("페이지 스크롤 중...")
    for i in range(8):  # 스크롤 횟수 증가
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {(i + 1) / 8});")
        time.sleep(3)  # 각 스크롤 후 대기 시간 증가
        remove_image_verify_popup(driver)
        # '더보기' 버튼은 최대 2번까지만 클릭
        if SHOW_MORE_CLICKS < MAX_SHOW_MORE_CLICKS:
            click_show_more_buttons(driver)
    
    # 페이지 최상단으로 스크롤
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(3)
    
    # 페이지 소스 파싱
    print("페이지 소스 파싱 중...")
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, "html.parser")
    
    # HTML 파일로 저장
    html_path = os.path.join(base_download_folder, "page.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(soup.prettify())
    print(f"HTML 파일 저장됨: {html_path}")
    
    # 디버깅을 위한 페이지 스크린샷
    screenshot_path = os.path.join(base_download_folder, "page_screenshot.png")
    driver.save_screenshot(screenshot_path)
    print(f"스크린샷 저장됨: {screenshot_path}")
    
    # JavaScript 실행하여 동적 데이터 추출
    print("동적 데이터 추출 중...")
    page_data = driver.execute_script("""
        return {
            title: document.querySelector('h1')?.textContent,
            images: Array.from(document.querySelectorAll('img')).filter(img => {
                // 작은 이미지와 아이콘 필터링
                const rect = img.getBoundingClientRect();
                return rect.width > 100 && rect.height > 100 && !img.src.includes('icon') && !img.src.includes('logo');
            }).map(img => img.src),
            videos: Array.from(document.querySelectorAll('video, video source')).map(video => video.src || video.currentSrc)
        }
    """)
    
    # 추출된 데이터 저장
    with open(os.path.join(base_download_folder, "page_data.json"), "w", encoding="utf-8") as f:
        json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    # 상품 제목 추출
    title_element = (
        soup.find("h1", class_="product-title-text") or
        soup.find("h1", class_="detail-title") or
        soup.find("h1") or
        driver.find_element(By.TAG_NAME, "h1")
    )
    
    if title_element:
        if isinstance(title_element, webdriver.remote.webelement.WebElement):
            product_title = title_element.text.strip()
        else:
            product_title = title_element.get_text().strip()
    else:
        product_title = page_data.get('title', "Unknown Product").strip()
    
    print(f"상품 제목: {product_title}")
    
    # 상품별 폴더 생성
    product_folder = create_download_folder(base_download_folder, product_title)
    
    # 이미지 URL 수집 및 필터링
    image_urls = set()
    # BeautifulSoup으로 이미지 찾기
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src:
            image_urls.add(src)
    
    # JavaScript로 찾은 이미지 추가 (이미 필터링됨)
    image_urls.update(page_data.get('images', []))
    
    # 이미지 다운로드
    print(f"발견된 이미지 수: {len(image_urls)}")
    for i, img_url in enumerate(image_urls):
        if img_url and not img_url.startswith("data:"):
            if not img_url.startswith(('http://', 'https://')):
                img_url = urljoin(search_url, img_url)
            print(f"이미지 다운로드 중 ({i+1}/{len(image_urls)}): {img_url}")
            download_file(img_url, product_folder, f"image_{i+1}.jpg")
            # 과도한 요청 방지를 위한 대기
            time.sleep(0.5)
    
    # 비디오 URL 수집
    video_urls = set()
    
    # BeautifulSoup으로 비디오 찾기
    for video in soup.find_all(["video", "source"]):
        src = video.get("src") or video.get("data-src")
        if src:
            video_urls.add(src)
    
    # JavaScript로 찾은 비디오 추가
    video_urls.update(page_data.get('videos', []))
    
    # 추가 비디오 URL 검색 - 원본 파일에서 복원
    try:
        print("추가 비디오 요소 검색 중...")
        video_elements = driver.find_elements(By.TAG_NAME, "video")
        for video in video_elements:
            try:
                video_url = video.get_attribute("src")
                if video_url:
                    video_urls.add(video_url)
                    print(f"비디오 URL 발견: {video_url}")
                
                # source 태그 검색
                source_elements = video.find_elements(By.TAG_NAME, "source")
                for source in source_elements:
                    source_url = source.get_attribute("src")
                    if source_url:
                        video_urls.add(source_url)
                        print(f"비디오 소스 URL 발견: {source_url}")
            except:
                continue
        
        # iframe 내의 비디오 검색 시도
        iframe_elements = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframe_elements:
            try:
                # iframe으로 전환
                driver.switch_to.frame(iframe)
                
                # iframe 내부의 비디오 요소 검색
                iframe_videos = driver.find_elements(By.TAG_NAME, "video")
                for video in iframe_videos:
                    video_url = video.get_attribute("src")
                    if video_url:
                        video_urls.add(video_url)
                        print(f"iframe 내 비디오 URL 발견: {video_url}")
                
                # 원래 컨텍스트로 복귀
                driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                continue
    except Exception as e:
        print(f"추가 비디오 검색 중 오류: {e}")
    
    # 동영상 컨테이너 내 src 검색 (data-video 속성 등)
    try:
        print("동영상 컨테이너 속성 검색 중...")
        video_containers = driver.find_elements(By.CSS_SELECTOR, "[class*='video'], [data-video], [class*='player']")
        for container in video_containers:
            try:
                # data-video 또는 data-src 속성 확인
                data_video = container.get_attribute("data-video")
                if data_video and (data_video.startswith('http') or data_video.startswith('//')):
                    fixed_url = data_video if data_video.startswith('http') else f"https:{data_video}"
                    video_urls.add(fixed_url)
                    print(f"data-video URL 발견: {fixed_url}")
                
                # 스크립트 데이터에서 video_url 추출 시도
                container_html = container.get_attribute('outerHTML')
                if container_html and ('videoUrl' in container_html or 'videourl' in container_html.lower()):
                    # JavaScript 실행으로 데이터 추출 시도
                    try:
                        video_data = driver.execute_script("""
                            var el = arguments[0];
                            var videoData = null;
                            
                            // dataset에서 정보 찾기
                            if (el.dataset.video) return el.dataset.video;
                            
                            // 스크립트 태그에서 찾기
                            var scripts = document.querySelectorAll('script');
                            for (var i = 0; i < scripts.length; i++) {
                                var content = scripts[i].textContent;
                                if (content && (content.indexOf('videoUrl') > -1 || content.indexOf('videourl') > -1)) {
                                    try {
                                        var match = content.match(/['"](https?:[^'"]+\\.mp4)['"]/);
                                        if (match) return match[1];
                                    } catch(e) {}
                                }
                            }
                            
                            return null;
                        """, container)
                        
                        if video_data and isinstance(video_data, str) and video_data.startswith('http'):
                            video_urls.add(video_data)
                            print(f"스크립트에서 발견된 비디오 URL: {video_data}")
                    except:
                        pass
            except:
                continue
    except Exception as e:
        print(f"동영상 컨테이너 검색 중 오류: {e}")
    
    # 비디오 다운로드 (개선된 방식)
    print(f"발견된 비디오 수: {len(video_urls)}")
    for i, video_url in enumerate(video_urls):
        if video_url and not video_url.startswith("data:"):
            if not video_url.startswith(('http://', 'https://')) and video_url.startswith('//'):
                video_url = f"https:{video_url}"
            elif not video_url.startswith(('http://', 'https://')):
                video_url = urljoin(search_url, video_url)
            
            print(f"비디오 다운로드 중 ({i+1}/{len(video_urls)}): {video_url}")
            result = download_file(video_url, product_folder, f"video_{i+1}.mp4")
            if result:
                print(f"비디오 다운로드 성공: {result}")
            else:
                print(f"비디오 다운로드 실패: {video_url}")
            time.sleep(1)  # 다운로드 간 간격

    print(f"다운로드 완료! 폴더 위치: {product_folder}")

    # 상품 상세 정보 저장
    save_product_details(driver, product_folder)

except Exception as e:
    print(f"처리 중 오류 발생: {e}")
    import traceback
    print(traceback.format_exc())

finally:
    driver.quit() 

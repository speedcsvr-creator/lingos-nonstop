import json
import os
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

LOGIN_URL = "https://lingos.pl/h/login"

class LingosContinuousBot:
    def __init__(self):
        self.dictionary = {"zwiedzać": "go sightseeing"}
        self.synonyms = {
            "seldom": "rarely", "rarely": "seldom", "hang out": "spend time",
            "gran": "granny", "granny": "gran", "Computer Studies": "IT or ICT",
            "type": "kind", "kind": "type", "do the washing": "do the laundry",
            "do the laundry": "do the washing", "a little": "a bit",
            "take out the rubbish": "empty the bin", "messy": "untidy",
            "hang out with": "spend time with"
        }

        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.page_load_strategy = 'eager'

        self.driver = webdriver.Chrome(options=options)
        self.last_url_log = ""

    def handle_login(self):
        login_val = os.getenv("LINGOS_LOGIN")
        pass_val = os.getenv("LINGOS_PASSWORD")
        
        print("[+] Logowanie do Lingos...")
        self.driver.get(LOGIN_URL)
        time.sleep(3)

        if login_val and pass_val:
            try:
                js_login = f"""
                let inputs = document.querySelectorAll('input');
                let loginSet = false, passSet = false;
                for (let inp of inputs) {{
                    let type = inp.type.toLowerCase();
                    let name = (inp.name || '').toLowerCase();
                    if (!loginSet && (type === 'text' || type === 'email' || name.includes('login') || name.includes('email'))) {{
                        let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        nativeSetter.call(inp, {json.dumps(login_val)});
                        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        loginSet = true;
                    }} else if (!passSet && type === 'password') {{
                        let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        nativeSetter.call(inp, {json.dumps(pass_val)});
                        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        passSet = true;
                    }}
                }}
                let form = document.querySelector('form');
                if (form) {{
                    form.requestSubmit ? form.requestSubmit() : form.submit();
                }}
                """
                self.driver.execute_script(js_login)
                time.sleep(4)
                print(f"[+] Zalogowano. Pozycja startowa: {self.driver.current_url}")
            except Exception as e:
                print(f"[!] Błąd logowania: {e}")

    def fast_inject_answer_and_submit(self, answer_text=""):
        js = f"""
        let input = document.getElementById('learning-answer') || document.getElementById('flashcard_answer_input') || document.querySelector("input[type='text']");
        if (input) {{
            let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
            nativeSetter.call(input, {json.dumps(answer_text)});
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            let form = input.closest('form');
            if (form) {{
                form.requestSubmit ? form.requestSubmit() : form.submit();
            }} else {{
                input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }}));
            }}
        }}
        """
        try:
            self.driver.execute_script(js)
        except Exception:
            pass

    def fast_confirm_next(self):
        js = """
        let btns = document.querySelectorAll("button, a.btn");
        for (let btn of btns) {
            let txt = btn.innerText ? btn.innerText.toLowerCase() : '';
            if (txt.includes("dalej") || txt.includes("przejdź") || txt.includes("kontynuuj") || txt.includes("sprawdź")) {
                btn.click();
                return;
            }
        }
        """
        try:
            self.driver.execute_script(js)
        except Exception:
            pass

    def extract_and_learn_in_ram(self, question):
        js_extract = """
        let targets = document.querySelectorAll('strong, .text-foreground strong, #flashcard_correct_answer, .correct-answer');
        for (let t of targets) {
            let txt = t.innerText ? t.innerText.trim() : '';
            if (txt.length > 0 && !txt.toLowerCase().includes('prawidłowa')) return txt;
        }
        let alert = document.querySelector('.text-foreground, #flashcard_correct_answer');
        if (alert && alert.innerText) return alert.innerText.trim();
        return null;
        """
        start_time = time.time()
        while time.time() - start_time < 0.8:
            try:
                res = self.driver.execute_script(js_extract)
                if res:
                    cleaned = re.sub(r'^(Prawidłowa odpowiedź:|Odpowiedź:)\s*', '', res, flags=re.IGNORECASE).strip()
                    if cleaned and cleaned.lower() != question.lower():
                        self.dictionary[question] = cleaned
                        print(f"[RAM BAZA] Zapamiętano: '{question}' -> '{cleaned}'")
                        break
            except Exception:
                pass
            time.sleep(0.02)

    def process_navigation(self):
        js = """
        let links = document.querySelectorAll("a, button");
        for (let l of links) {
            let href = l.getAttribute('href') || '';
            let txt = l.innerText ? l.innerText.toLowerCase() : '';
            if (href.includes('/learning') || href.includes('/lesson') || href.includes('/start') || 
                txt.includes("ucz się") || txt.includes("rozpocznij") || txt.includes("wykonaj") || txt.includes("lekcja")) {
                l.click();
                return true;
            }
        }
        return false;
        """
        try:
            return self.driver.execute_script(js)
        except Exception:
            return False

    def get_question(self):
        selectors = [
            (By.XPATH, "//p[contains(@class, 'text-2xl')]"),
            (By.XPATH, "//div[contains(@class, 'text-2xl')]"),
            (By.ID, "flashcard_main_text"),
            (By.CLASS_NAME, "flashcard-text")
        ]
        for by, sel in selectors:
            els = self.driver.find_elements(by, sel)
            for el in els:
                if el.is_displayed() and el.text.strip():
                    return el.text.strip()
        return None

    def run(self, duration_hours=5):
        self.handle_login()
        start_time = time.time()
        max_seconds = duration_hours * 3600

        print(f"[+] Rozpoczynam wykonywanie zadań (Czas: {duration_hours}h)...")

        nav_retry = 0
        while time.time() - start_time < max_seconds:
            try:
                question = self.get_question()

                if not question:
                    self.process_navigation()
                    time.sleep(0.2)
                    
                    nav_retry += 1
                    if nav_retry % 15 == 0:
                        curr_url = self.driver.current_url
                        if curr_url != self.last_url_log:
                            print(f"[+] Bot szuka lekcji na stronie: {curr_url}")
                            self.last_url_log = curr_url
                    continue

                nav_retry = 0
                answer = None

                if "is a synonym for" in question:
                    match = re.search(r'"([^"]+)"', question)
                    target = match.group(1) if match else ""
                    answer = self.synonyms.get(target)
                elif question in self.dictionary:
                    answer = self.dictionary[question]

                if answer:
                    print(f"[+] Odpowiedź na '{question}' -> '{answer}'")
                    self.fast_inject_answer_and_submit(answer)
                    self.fast_confirm_next()
                    time.sleep(0.05)
                    continue

                print(f"[?] Nieznane słówko '{question}' -> Pobieram odpowiedź...")
                self.fast_inject_answer_and_submit("")
                self.extract_and_learn_in_ram(question)
                self.fast_confirm_next()

            except Exception as e:
                time.sleep(0.1)

        print("[+] Koniec cyklu.")
        self.driver.quit()

if __name__ == "__main__":
    bot = LingosContinuousBot()
    bot.run(duration_hours=5)

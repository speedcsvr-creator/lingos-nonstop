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

    def handle_login(self):
        login_val = os.getenv("LINGOS_LOGIN")
        pass_val = os.getenv("LINGOS_PASSWORD")
        
        print("[+] Logowanie do Lingos (JS Direct Injection)...")
        self.driver.get(LOGIN_URL)
        time.sleep(3)

        if login_val and pass_val:
            try:
                # Wstrzyknięcie loginu i hasła bezpośrednio w DOM (omija błędy Selenium)
                js_login = f"""
                let inputs = document.querySelectorAll('input');
                let loginSet = false;
                let passSet = false;
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
                print("[+] Zalogowano pomyślnie! Rozpoczynam pętlę TURBO...")
            except Exception as e:
                print(f"[!] Błąd logowania: {e}")

    def fast_inject_answer_and_submit(self, answer_text=""):
        js = f"""
        let input = document.getElementById('learning-answer') || document.getElementById('flashcard_answer_input');
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
        let btn = document.querySelector("button[type='submit'], button:not([disabled])");
        if (btn && (btn.innerText.includes("Dalej") || btn.innerText.includes("Przejdź"))) {
            btn.click();
        }
        """
        try:
            self.driver.execute_script(js)
        except Exception:
            pass

    def extract_and_learn_in_ram(self, question):
        js_extract = """
        let targets = document.querySelectorAll('strong, .text-foreground strong, #flashcard_correct_answer');
        for (let t of targets) {
            let txt = t.innerText ? t.innerText.trim() : '';
            if (txt.length > 0 && !txt.toLowerCase().includes('prawidłowa')) return txt;
        }
        let alert = document.querySelector('.text-foreground, #flashcard_correct_answer');
        if (alert && alert.innerText) return alert.innerText.trim();
        return null;
        """
        start_time = time.time()
        while time.time() - start_time < 1.0:
            try:
                res = self.driver.execute_script(js_extract)
                if res:
                    cleaned = re.sub(r'^(Prawidłowa odpowiedź:|Odpowiedź:)\s*', '', res, flags=re.IGNORECASE).strip()
                    if cleaned and cleaned.lower() != question.lower():
                        self.dictionary[question] = cleaned
                        print(f"[RAM BAZA] Zapamiętano: {question} -> {cleaned}")
                        break
            except Exception:
                pass
            time.sleep(0.02)

    def process_navigation(self):
        js = """
        let link = document.querySelector("a[href*='/learning/start'], a[href*='/s/lesson']");
        if (link) { link.click(); return true; }
        return false;
        """
        try:
            return self.driver.execute_script(js)
        except Exception:
            return False

    def get_question(self):
        selectors = [(By.XPATH, "//p[contains(@class, 'text-2xl')]"), (By.ID, "flashcard_main_text")]
        for by, sel in selectors:
            els = self.driver.find_elements(by, sel)
            if els and els[0].is_displayed():
                return els[0].text.strip()
        return None

    def run(self, duration_hours=5):
        self.handle_login()
        start_time = time.time()
        max_seconds = duration_hours * 3600

        print(f"[+] Bot uruchomiony w trybie ciągłym na {duration_hours} godzin...")

        while time.time() - start_time < max_seconds:
            try:
                self.process_navigation()
                question = self.get_question()

                if not question:
                    time.sleep(0.05)
                    continue

                answer = None
                if "is a synonym for" in question:
                    match = re.search(r'"([^"]+)"', question)
                    target = match.group(1) if match else ""
                    answer = self.synonyms.get(target)
                elif question in self.dictionary:
                    answer = self.dictionary[question]

                if answer:
                    self.fast_inject_answer_and_submit(answer)
                    self.fast_confirm_next()
                    time.sleep(0.03)
                    continue

                self.fast_inject_answer_and_submit("")
                self.extract_and_learn_in_ram(question)
                self.fast_confirm_next()

            except Exception:
                time.sleep(0.05)

        print("[+] Koniec cyklu.")
        self.driver.quit()

if __name__ == "__main__":
    bot = LingosContinuousBot()
    bot.run(duration_hours=5)

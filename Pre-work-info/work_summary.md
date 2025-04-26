# Arbetsöversikt: Chatib Bot-projektet

Detta dokument sammanfattar arbetet som utförts hittills och de återstående stegen för att färdigställa Chatib-boten.

## Utfört Arbete

1.  **Planering och Arkitektur:**
    *   Analyserat kraven från `bot_summary.md`.
    *   Diskuterat och fastställt en projektstruktur och teknikval (Python, Flask, Selenium, Multiprocessing).
    *   Definierat utvecklingssteg i `stepinstructions.md`.
    *   Verifierat nödvändiga XPath-selektorer från `xpaths_registration.md` och `xpaths_interaction.md`.

2.  **Grundläggande Struktur och Konfiguration (Fas 1):**
    *   Skapat mappstrukturen (`app`, `data`, undermappar) och `__init__.py`-filer.
    *   Skapat `requirements.txt` med nödvändiga paket (Flask, Selenium, requests).
    *   Skapat `setup.bat` för att hantera virtuell miljö och installation av beroenden.
    *   **Körexekvering:** Kört `setup.bat` för att skapa `venv` och installera paketen.
    *   Implementerat konfigurationshanteraren (`app/config/manager.py`) för att läsa/skriva `config.json` och `messages.txt`.

3.  **Kärnlogik för Boten (Fas 2):**
    *   Implementerat AdsPower API-integration för att starta/stoppa webbläsare och grundläggande Selenium-hjälpfunktioner i `app/bot_core/selenium_handler.py`.
    *   Implementerat logik för registrering och omregistrering (inklusive felhantering för användarnamn) i `app/bot_core/registration.py`.
    *   Implementerat logik för chattinteraktion (navigering, hitta användare, skicka meddelanden, fas-hantering, vänta på svar, upptäcka utloggning, rapportera statistik via kö) i `app/bot_core/chat_logic.py`.

4.  **Konkurrens och Dashboard (Fas 3):**
    *   Implementerat konkurrenshanteraren (`app/concurrency/manager.py`) för att starta, stoppa och övervaka flera bot-processer med `multiprocessing` och aggregera statistik från en kö.
    *   Implementerat Flask-routes (`app/dashboard/routes.py`) för att visa dashboarden, hantera konfigurationssparande, starta/stoppa botar och tillhandahålla en statistik-endpoint.
    *   Skapat HTML-mallen (`app/dashboard/templates/index.html`) för dashboarden med formulär för konfiguration, knappar för kontroll och JavaScript för att uppdatera statistik i realtid.

5.  **Sammankoppling (Del av Fas 4):**
    *   Skapat startpunkten (`app/main.py`) som initierar Flask-appen och konkurrenshanteraren, samt inkluderar logik för att försöka stoppa botar vid avslut.

6.  **Förbättringar och Korrigeringar (2025-04-24):**
    *   **Linting:** Åtgärdat diverse mindre varningar.
    *   **State Management:** Klargjort lokal state-hantering och aggregering via kö.
    *   **Dashboard Input:** Uppdaterat `index.html` för `<textarea>` för listor.
    *   **Konfigurationssparande:** Uppdaterat `routes.py` för listor.
    *   **Unika Registreringsstäder:** Implementerat logik för att tilldela unika städer per bot.
    *   **Användarnamnslista för Registrering:** Implementerat funktionalitet för att använda en fördefinierad lista med användarnamn vid registrering (`config/manager.py`, `index.html`, `routes.py`, `concurrency/manager.py`, `chat_logic.py`, `registration.py`).

7.  **Felsökning och Robusthet (2025-04-25):**
    *   **Meddelandefaser (Phase Tracking):**
        *   Modifierat `chat_logic.py` för att endast skicka mellanliggande faser (efter första, före sista 3) om användaren har svarat sedan botens senaste meddelande (baserat på antal inkommande meddelanden). Första och sista 3 faserna skickas oavsett svar.
        *   Lagt till 10 sekunders paus (`time.sleep(10)`) efter att de sista 3 faserna skickats.
        *   Förbättrat User ID-extraktion i `chat_logic.py` (`click_user_and_get_id`) för att prioritera `data-id` från det klickade `<li>`-elementet eller dess förälder, med URL som fallback.
        *   Lagt till detaljerad loggning i `chat_logic.py` för att spåra cykler, state-ordlistor, extraherade User IDs och fasuppdateringar för felsökning.
    *   **Subprocess Importer:** Korrigerat `ModuleNotFoundError: No module named 'app'` i underprocesser genom att lägga till projektets rotkatalog i `sys.path` i början av `run_bot_instance` i `concurrency/manager.py`.
    *   **AdsPower WebDriver-anslutning:** Korrigerat `invalid argument: cannot parse debuggerAddress` i `selenium_handler.py` genom att skicka `debuggerAddress` (som innehåller `host:port`) direkt till Selenium Options.
    *   **Popup-hantering vid start:**
        *   Lagt till logik i `run_bot_instance` (`concurrency/manager.py`) för att hantera Google Consent-popupen direkt efter sidladdning, med specifika XPaths och JS-klick som fallback. Logik för att söka i iframes togs bort då specifika XPaths angavs.
        *   Lagt till logik i `run_bot_instance` för att hantera Chatib Terms-popupen efter eventuell registrering.
    *   **Registreringsfel (Captcha):** Uppdaterat `registration.py` för att upptäcka "Invalid Captcha"-felet (`//div[@class='alert alert-danger']`) efter `attempt_registration` och initiera ett nytt registreringsförsök (liknande hanteringen av upptaget användarnamn).
    *   **Sidans Laddningsstrategi:** Ändrat Seleniums `page_load_strategy` till `eager` i `selenium_handler.py` för att potentiellt snabba upp interaktioner genom att inte vänta på att alla resurser (bilder, CSS) laddats klart.
    *   **Ad-hantering & Refresh:**
        *   Lagt till proaktiv kontroll i början av `handle_chat_cycle` (`chat_logic.py`) för att upptäcka `#google_vignette` i URL:en och initiera en siduppdatering (`driver.refresh()`).
        *   Förbättrat väntetider efter alla `driver.refresh()` (både proaktiv och vid fel) i `chat_logic.py` genom att använda `WebDriverWait` för att vänta på att inkorgsknappen blir klickbar (upp till 60 sekunder), istället för fast `time.sleep()`.
    *   **Användarnamnslista (Felsökning):** Lagt till detaljerad loggning i `registration.py` (`[REG_DEBUG]`) för att verifiera att listan tas emot och används korrekt innan fallback till slumpmässiga namn sker.

8.  **Felsökning och Robusthet - Konkurrens (2025-04-26):**
    *   **Flexibel Startsekvens:** Implementerat en sekventiell startlogik (Consent -> Registrering -> Inloggad) i `app/concurrency/manager.py` för att hantera olika initiala sidtillstånd och förhindra fel när consent-popupen inte är närvarande.
    *   **Verifierad Multi-Instance Start:** Bekräftat att flera bot-instanser nu startar, registrerar sig och kör chat-cykeln korrekt med den nya startlogiken.

9.  **Individuell Bot-loggning till Dashboard (2025-04-26):**
    *   **Logghantering:** Implementerat en separat `multiprocessing.Queue` (`log_queue`) för loggmeddelanden i `app/concurrency/manager.py`.
    *   **Lagring:** `ConcurrencyManager` lagrar nu loggar per bot-ID i `self.bot_logs` (med en maxgräns per bot) genom att läsa från `log_queue`.
    *   **Bot-modifieringar:** Uppdaterat `run_bot_instance` (`manager.py`), `handle_chat_cycle` (`chat_logic.py`), `handle_registration_process` (`registration.py`) samt diverse hjälpfunktioner i `registration.py` och `selenium_handler.py` för att acceptera och använda `log_queue` för loggning istället för `print`.
    *   **Dashboard:**
        *   Lagt till en ny Flask-route (`/logs/<bot_id>`) i `app/dashboard/routes.py` för att hämta loggar för en specifik bot via `concurrency_manager.get_logs()`.
        *   Uppdaterat `app/dashboard/templates/index.html` med en dropdown (`<select>`) för att välja bot-ID (populeras dynamiskt från `/get_stats`) och en `<pre>`-tagg för att visa loggarna.
        *   Implementerat JavaScript i `index.html` för att hämta och visa loggar periodiskt för den valda boten.

10. **Individuell Bot-kontroll & Felsökning (2025-04-26):**
    *   **Refaktorering (Windows Multiprocessing):** Flyttat `run_bot_instance`-funktionen från `app/concurrency/manager.py` till en ny fil `app/concurrency/bot_runner.py` för att potentiellt lösa problem med subprocess-initiering på Windows.
    *   **Felsökning (Startproblem):** Utfört diverse felsökningssteg (loggning, förenkling, test av `log_queue`) för att identifiera varför bot-processer inte startade korrekt. Problemet visade sig bero på en extern AdsPower-uppdatering.
    *   **Individuell Stopp:**
        *   Modifierat `app/concurrency/manager.py` för att använda en dictionary (`profile_id -> Process`) för att spåra processer.
        *   Implementerat `stop_bot(profile_id)`-metod i `app/concurrency/manager.py`.
        *   Lagt till Flask-route `/stop_bot/<profile_id>` i `app/dashboard/routes.py`.
        *   Uppdaterat `app/dashboard/templates/index.html` för att visa aktiva botar som en lista med individuella stoppknappar och tillhörande JavaScript.
    *   **Bugfix (`get_stats`):** Korrigerat `TypeError` i `app/concurrency/manager.py` som uppstod vid sortering av bot-ID:n om listan innehöll `None`.

11. **Headless Mode Toggle (2025-04-26):**
    *   **Konfiguration:** Lagt till `run_headless` (boolean) i `data/config.json` och uppdaterat `app/config/manager.py` för att hantera standardvärdet.
    *   **Dashboard UI:** Lagt till en kryssruta i `app/dashboard/templates/index.html` för att aktivera/inaktivera headless mode.
    *   **Dashboard Backend:** Uppdaterat `app/dashboard/routes.py` (`save_config_route`) för att läsa och spara kryssrutans värde till konfigurationen.
    *   **AdsPower Integration:** Modifierat `start_adspower_browser` i `app/bot_core/selenium_handler.py` för att läsa `run_headless`-inställningen och lägga till `&headless=1` i AdsPower API-anropet om inställningen är aktiverad.

12. **Robusthet vid Registrering (2025-04-26):**
    *   **Verifiering efter "Start Chat Now":** Lagt till en kontroll i `attempt_registration` (`app/bot_core/registration.py`) direkt efter att "Start Chat Now"-knappen klickats. Kontrollen verifierar att användarnamnsfältet (`//input[@id='username']`) *inte* längre finns på sidan (med en kort timeout). Om fältet fortfarande finns, indikerar det att inloggningen/sidbytet misslyckades, och funktionen returnerar `False`. Detta ökar robustheten mot oväntade fel eller ändringar på registreringssidan.

## Återstående Arbete och Nästa Steg

1.  **Multi-Instance Testing:**
    *   Verifiera att den nya sekventiella startlogiken fungerar stabilt för flera instanser under längre körningar.
    *   Övervaka resursanvändning (CPU, RAM) och potentiella flaskhalsar vid samtidig körning.
    *   Verifiera att `user_ids.json` hanteras korrekt vid samtidig läsning/skrivning (konkurrens).
    *   Verifiera att dashboard-statistiken aggregeras korrekt från alla instanser.

2.  **Dashboard Förbättringar & Failsafe (Nästa Fokus):**
    *   **Statistik - "Konversationer Startade":** Implementera logik för att räkna och visa när en bot skickar det *första* meddelandet (fas 0) till en *ny* användare.
    *   **Automatisk Failsafe (Banned):** Implementera logik för att upptäcka om ett konto blivit blockerat (genom att söka efter nyckelord) och automatiskt starta om processen med ett nytt profil-ID från en backup-lista. (Kräver UI för backup-lista).
    *   **(Eventuellt) Individuell Start:** Utvärdera behovet och komplexiteten av att kunna starta en *enskild* bot manuellt.

3.  **Förfining och Robusthet:**
    *   Baserat på multi-instance-testning, justera eventuella väntetider (`time.sleep`, `WebDriverWait`-timeouts) för optimal prestanda och stabilitet.
    *   Om konkurrensproblem med `user_ids.json` uppstår, överväg mer robust fillåsning eller en annan state management-lösning.
    *   Förbättra felhantering ytterligare för oväntade scenarion.

4.  **Dokumentation:**
    *   Uppdatera `README.md` med slutgiltiga instruktioner när boten är stabil och de nya funktionerna är implementerade.

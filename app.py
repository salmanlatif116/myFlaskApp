from flask import Flask, json, request, jsonify, render_template
from flask_mail import Mail, Message
import re
import os
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from celery_config import celery_app


load_dotenv()

app = Flask(__name__)


# Email configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("EMAIL")
app.config["MAIL_PASSWORD"] = os.environ.get("PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("EMAIL")

mail = Mail(app)


# Configure Selenium ChromeDriver options
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


# Function to scrape emails from page source
@celery_app.task
def scrape_emails(page_source):
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    emails = re.findall(email_regex, page_source)
    all_emails = [
        email
        for email in emails
        if not (
            email.endswith(
                (
                    ".jpg",
                    ".png",
                    ".gif",
                    ".webp",
                    ".wixpress.com",
                    "sentry.io",
                    "example.com",
                )
            )
        )
    ]

    return list(set(all_emails))


# Asynchronous function to extract data from a URL
@celery_app.task
def extract_data_from_all_urls_of_website(url, driver):
    all_emails = []
    if not url.startswith("http"):
        url = "http://" + url

    try:
        print(f"[INFO] Visiting website: {url}")
        driver.get(url)
        emails = scrape_emails(driver.page_source)
        all_emails.extend(emails)

        # Look for 'About Us' and 'Contact Us' pages
        for page in ["About", "Contact"]:
            try:
                page_link = driver.find_element(
                    By.XPATH,
                    f"//a[contains(text(), '{page}') or contains(text(), '{page} Us')]",
                )
                page_url = page_link.get_attribute("href")
                if page_url:
                    driver.get(page_url)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    emails = scrape_emails(driver.page_source)
                    all_emails.extend(emails)
            except (NoSuchElementException, TimeoutException):
                print(f"[INFO] '{page} Us' page not found.")

        # Extract all links from the webpage
        hrefs = set()
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href:
                href = urljoin(url, href)
                href = urlparse(href)._replace(fragment="").geturl()
                hrefs.add(href)

        print("[INFO] Extracting all possible emails.")
        visited_links = set()

        for href in hrefs:
            if (
                href
                and href not in visited_links
                and not href.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv"))
            ):
                visited_links.add(href)
                retries = 3  # Retry mechanism for visiting links

                while retries > 0:
                    try:
                        driver.get(href)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        emails = scrape_emails(driver.page_source)
                        all_emails.extend(emails)
                        break

                    except StaleElementReferenceException:
                        retries -= 1
                    except (NoSuchElementException, TimeoutException):
                        break
                    except Exception:
                        break

    except Exception as e:
        print(f"[ERROR] Failed to load the website {url}: {e}")

    unique_emails = list(set(all_emails))
    with open("detail_emails.txt", "a") as file:
        for email in unique_emails:
            file.write(email + "\n")

    return {"Emails": unique_emails}


@celery_app.task
async def extract_data_from_home_about_contact_page(url, driver):
    all_emails = []
    if not url.startswith("http"):
        url = "http://" + url

    try:
        print(f"[INFO] Visiting website: {url}")
        driver.get(url)
        emails = scrape_emails(driver.page_source)
        all_emails.extend(emails)

        # Look for 'About Us' page
        print("[INFO] Looking for 'About Us' page for email...")
        try:
            about_us_link = driver.find_element(
                By.XPATH,
                "//a[contains(text(), 'About') or contains(text(), 'About Us')]",
            )
            about_us_url = about_us_link.get_attribute("href")
            if about_us_url:
                driver.get(about_us_url)
                emails = scrape_emails(driver.page_source)
                all_emails.extend(emails)
        except (NoSuchElementException, TimeoutException):
            print("[INFO] 'About Us' page not found.")

        # Look for 'Contact Us' page
        print("[INFO] Looking for 'Contact Us' page for email...")
        try:
            contact_us_link = driver.find_element(
                By.XPATH,
                "//a[contains(text(), 'Contact') or contains(text(), 'Contact Us')]",
            )
            contact_us_url = contact_us_link.get_attribute("href")
            if contact_us_url:
                driver.get(contact_us_url)
                emails = scrape_emails(driver.page_source)
                all_emails.extend(emails)
        except (NoSuchElementException, TimeoutException):
            print("[INFO] 'Contact Us' page not found.")

    except (
        TimeoutException,
        NoSuchElementException,
        StaleElementReferenceException,
        Exception,
    ) as e:
        print(f"[ERROR] Failed to load the website {url}: {e}")

    unique_emails = list(set(all_emails))
    with open("about_contact_emails.txt", "a") as file:
        for email in unique_emails:
            file.write(email + "\n")
    return {"Emails": unique_emails}


# Function to send the scraped emails file as an attachment
@celery_app.task
async def send_email_with_attachment():
    recipient = "salmanlatif@tekvix.com"
    attachments = []
    if os.path.exists("about_contact_emails.txt"):
        attachments.append("about_contact_emails.txt")

    if os.path.exists("detail_emails.txt"):
        attachments.append("detail_emails.txt")

    for attachment in attachments:
        if attachment.endswith("detail_emails.txt"):
            subject = "Scraped Detail Emails"
        elif attachment.endswith("about_contact_emails.txt"):
            subject = "Scraped About & Contact Emails"
        else:
            print(f"[WARNING] Unknown file type for '{attachment}'. Skipping...")
            continue
        msg = Message(subject, recipients=[recipient])
        msg.body = "Please find the attached file with scraped emails."

        if not os.path.exists(attachment):
            print(f"[WARNING] Attachment '{attachment}' does not exist. Skipping...")
            continue

        with app.open_resource(attachment) as fp:
            msg.attach(attachment, "text/plain", fp.read())

        try:
            mail.send(msg)
            print("[INFO] Email with attachment sent successfully!")
            os.remove(attachment)

        except Exception as e:
            print(f"[ERROR] Failed to send email: {e}")


@celery_app.task
def load_google_maps(driver):
    print("[INFO] Loading Google Maps...")
    driver.get("https://www.google.com/maps")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "searchboxinput"))
    )
    print("[INFO] Google Maps loaded successfully.")


@celery_app.task
def search_query(driver, query):
    print(f"[INFO] Searching for query: {query}")
    search_box = driver.find_element(By.ID, "searchboxinput")
    search_box.send_keys(query)
    search_button = driver.find_element(By.ID, "searchbox-searchbutton")
    search_button.click()

    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "Nv2PK"))
        )
        print(f"[INFO] Search results loaded for: {query}")
    except TimeoutException:
        print(
            f"[ERROR] No results found for the query: {query}. Please try a different query."
        )
        driver.quit()
        return


@celery_app.task
def scroll_and_collect_listings(driver, wait_time=15):
    listings = []
    previous_listing_count = 0
    attempts = 0

    print("[INFO] Scrolling through listings...")
    while True:
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(wait_time)
        new_listings = driver.find_elements(By.CLASS_NAME, "Nv2PK")

        if new_listings:
            driver.execute_script("arguments[0].scrollIntoView();", new_listings[-1])
            print(f"[INFO] Scrolled to {len(new_listings)} listings.")

        if len(new_listings) == previous_listing_count:
            print(f"[INFO] No more new listings found after {attempts} attempts.")
            break

        previous_listing_count = len(new_listings)
        attempts += 1
        if attempts >= 20:
            print("[WARNING] Reached maximum scroll attempts.")
            break

    print(f"[INFO] Total listings collected: {len(new_listings)}")
    return new_listings


@celery_app.task
async def extract_listing_data_for_about_contact(listing, index, driver):
    try:
        all_urls = []
        print(f"[INFO] Extracting data for listing {index + 1}")
        
        try:
            website_element = listing.find_element(By.CSS_SELECTOR, "a.lcr4fd.S9kvJb")
            website_url = (
                website_element.get_attribute("href") if website_element else "N/A"
            )
        except NoSuchElementException:
            website_url = "N/A"

        all_emails = []
        if website_url != 'N/A':
            try:
                print(f"[INFO] Visiting website: {website_url}")
                original_window = driver.current_window_handle
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(website_url)

                emails = scrape_emails(driver.page_source)
                all_emails.extend(emails)

                # Look for 'About Us' page
                print("[INFO] Looking for 'About Us' page for email...")
                try:
                    about_us_link = driver.find_element(By.XPATH, "//a[contains(text(), 'About') or contains(text(), 'About Us')]")
                    about_us_url = about_us_link.get_attribute('href')
                    if about_us_url:
                        driver.get(about_us_url)
                        emails = scrape_emails(driver.page_source)
                        all_emails.extend(emails)
                except (NoSuchElementException, TimeoutException):
                    print("[INFO] 'About Us' page not found.")

                # Look for 'Contact Us' page
                print("[INFO] Looking for 'Contact Us' page for email...")
                try:
                    contact_us_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Contact') or contains(text(), 'Contact Us')]")
                    contact_us_url = contact_us_link.get_attribute('href')
                    if contact_us_url:
                        driver.get(contact_us_url)
                        emails = scrape_emails(driver.page_source)
                        all_emails.extend(emails)
                except (NoSuchElementException, TimeoutException):
                    print("[INFO] 'Contact Us' page not found.")

            except Exception as e:
                print(f"[ERROR] Failed to load the website {website_url}: {e}")
                all_emails = []
            finally:
                driver.close()
                driver.switch_to.window(original_window)

        unique_emails = list(set(all_emails))
        with open("about_contact_emails.txt", "a") as file:
            for email in unique_emails:
                file.write(email + "\n")

        return {"Emails": unique_emails}
    except StaleElementReferenceException:
        print(
            f"[ERROR] Stale element reference encountered while processing listing {index + 1}. Skipping this listing."
        )
        return None
    except Exception as e:
        print(
            f"[ERROR] An error occurred while extracting data from listing {index + 1}: {e}"
        )
        return None



@celery_app.task
async def extract_listing_data_for_all_urls(listing, index, driver):
    try:
        print(f"[INFO] Extracting data for listing {index + 1}")
        all_emails = []

        # Extract website URL
        try:
            website_element = listing.find_element(By.CSS_SELECTOR, "a.lcr4fd.S9kvJb")
            website_url = (
                website_element.get_attribute("href") if website_element else "N/A"
            )
        except NoSuchElementException:
            website_url = "N/A"

        if website_url != "N/A":
            try:
                print(f"[INFO] Visiting website: {website_url}")
                original_window = driver.current_window_handle
                driver.execute_script("window.open('');")  # Open a new tab for email scraping
                driver.switch_to.window(driver.window_handles[1])  # Switch to the new tab
                driver.get(website_url)

                # Scrape emails from the website's page source
                emails = scrape_emails(driver.page_source)
                all_emails.extend(emails)

                # Extract all links from the website
                hrefs = set()
                links = driver.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        href = urljoin(website_url, href)
                        href = urlparse(href)._replace(fragment="").geturl()
                        hrefs.add(href)

                print("[INFO] Extracting all possible emails from linked pages.")
                visited_links = set()

                # Visit each link to scrape emails
                for href in hrefs:
                    if (
                        href
                        and href not in visited_links
                        and not href.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv"))
                    ):
                        visited_links.add(href)
                        retries = 3  # Retry mechanism for visiting links

                        while retries > 0:
                            try:
                                driver.get(href)
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                                )
                                emails = scrape_emails(driver.page_source)
                                all_emails.extend(emails)
                                break
                            except StaleElementReferenceException:
                                retries -= 1
                            except (NoSuchElementException, TimeoutException):
                                break
                            except Exception as e:
                                print(f"[ERROR] Unexpected error for {href}: {e}")
                                break

            except Exception as e:
                print(f"[ERROR] Failed to load the website {website_url}: {e}")
            finally:
                driver.close()  # Close the tab with the website
                driver.switch_to.window(original_window)  # Switch back to the original tab

        # Save unique emails to file
        unique_emails = list(set(all_emails))
        with open("detail_emails.txt", "a") as file:
            for email in unique_emails:
                file.write(email + "\n")

        return {"Emails": unique_emails}

    except StaleElementReferenceException:
        print(
            f"[ERROR] Stale element reference encountered while processing listing {index + 1}. Skipping this listing."
        )
        return None
    except Exception as e:
        print(
            f"[ERROR] An error occurred while extracting data from listing {index + 1}: {e}"
        )
        return None


"""API Endpoint Defination"""
@celery_app.task
@app.route("/api/v1/scrape/google-map-about-contact/", methods=["POST"])
async def scrape_google_map():
    data = request.json
    query = data.get("query")

    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    driver = setup_driver()
    try:
        load_google_maps(driver)
        search_query(driver, query)
        listings = scroll_and_collect_listings(driver)
        listing_data_list = []

        for index, listing in enumerate(listings):
            try:
                data = await extract_listing_data_for_about_contact(listing, index, driver)
                if data:
                    listing_data_list.append(data)
            except Exception as e:
                print(
                    f"[ERROR] An error occurred while processing listing {index}: {e}"
                )

        await send_email_with_attachment()
        return jsonify(listing_data_list), 200
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500
    



@celery_app.task
@app.route("/api/v1/scrape/google-map-all-urls/", methods=["POST"])
async def scrape_google_map_all_urls():
    data = request.json
    query = data.get("query")

    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    driver = setup_driver()
    try:
        load_google_maps(driver)
        search_query(driver, query)
        listings = scroll_and_collect_listings(driver)
        listing_data_list = []

        for index, listing in enumerate(listings):
            try:
                data = await extract_listing_data_for_all_urls(listing, index, driver)
                if data:
                    listing_data_list.append(data)
            except Exception as e:
                print(
                    f"[ERROR] An error occurred while processing listing {index}: {e}"
                )

        json_data = json.dumps(listing_data_list, indent=4)
        await send_email_with_attachment()
        return jsonify(listing_data_list)
    except Exception as e:
        print(e)
        return None
  

# Flask route to scrape emails and send the file
@celery_app.task
@app.route("/api/v1/url/scrape-about-contact-and-send-emails/", methods=["POST"])
async def scrape_and_send_about_contact():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "Please provide a valid URL"}), 400

    driver = setup_driver()
    try:
        result = await extract_data_from_home_about_contact_page(url, driver)
        if result:
            print(f"results ====> {result}")
            await send_email_with_attachment()
        return jsonify(result)
    except Exception as e:
        print(e)
        


@celery_app.task
@app.route("/api/v1/url/scrape-all-and-send-emails/", methods=["POST"])
async def scrape_and_send_all():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "Please provide a valid URL"}), 400

    driver = setup_driver()
    try:
        result = await extract_data_from_all_urls_of_website(url, driver)
        if result:
            await send_email_with_attachment()
        return jsonify(result)
    except Exception as e:
        print(e)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

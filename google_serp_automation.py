"""
Google SERP Automation Script
This script automates Google search and scrapes organic search results
"""

import os
import time
import random
import urllib.parse
from typing import List, Optional, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup


class GoogleSerpAutomation:
    def __init__(self):
        """Initialize the Google SERP automation"""
        self.driver = None
        self.wait_timeout = 10

    def setup_driver(self):
        """Setup Chrome with headless config and anti-detection measures"""
        chrome_options = Options()

        # Headless mode - optimized for server environments
        chrome_options.add_argument("--headless=new")  # New headless mode
        chrome_options.add_argument("--no-sandbox")  # Required for running in container
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        chrome_options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")

        # Anti-detection measures
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # Realistic user agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        chrome_options.add_argument(f"--user-agent={user_agent}")

        # Additional anti-detection preferences
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Initialize the driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)

        # Remove webdriver flag using CDP (Chrome DevTools Protocol)
        try:
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
        except Exception as e:
            print(f"Warning: Could not execute CDP command: {e}")

    def _build_search_url(self, query: str, page: int, num_results: int, language: str) -> str:
        """Build Google search URL with query parameters"""
        base_url = "https://www.google.com/search"

        # Calculate offset for pagination
        start = (page - 1) * num_results

        # Build query parameters
        params = {
            'q': query,
            'num': num_results,
            'hl': language
        }

        # Add start parameter for pagination (only if not first page)
        if start > 0:
            params['start'] = start

        # Encode parameters
        query_string = urllib.parse.urlencode(params)

        return f"{base_url}?{query_string}"

    def _check_for_captcha(self) -> bool:
        """Check if CAPTCHA is present on page"""
        try:
            # Check for common CAPTCHA indicators
            page_source = self.driver.page_source.lower()

            # Check for CAPTCHA-related text
            captcha_indicators = [
                "unusual traffic",
                "not a robot",
                "captcha",
                "recaptcha",
                "g-recaptcha"
            ]

            for indicator in captcha_indicators:
                if indicator in page_source:
                    print(f"CAPTCHA detected: Found '{indicator}' in page")
                    return True

            # Check for CAPTCHA form elements
            try:
                self.driver.find_element(By.ID, "captcha-form")
                print("CAPTCHA detected: Found captcha-form element")
                return True
            except NoSuchElementException:
                pass

            return False

        except Exception as e:
            print(f"Error checking for CAPTCHA: {e}")
            return False

    def _parse_organic_results(self) -> List[dict]:
        """Extract organic search results from page"""
        results = []

        try:
            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')

            # Try multiple selectors to find result containers
            result_containers = []

            # Strategy 1: div.g (most common)
            result_containers = soup.select('div.g')

            # Strategy 2: div with data-sokoban-container attribute
            if not result_containers:
                result_containers = soup.select('div[data-sokoban-container]')

            # Strategy 3: Look for divs inside #search or #rso
            if not result_containers:
                search_div = soup.select_one('div#search, div#rso')
                if search_div:
                    result_containers = search_div.find_all('div', recursive=False)

            print(f"Found {len(result_containers)} potential result containers")

            position = 1
            for container in result_containers:
                try:
                    # Extract title - look for h3 tag
                    title_elem = container.find('h3')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    if not title:
                        continue

                    # Extract URL - look for anchor tag in various places
                    url = None
                    display_url = None

                    # Try to find URL in yuRUbf div
                    yuRUbf_div = container.find('div', class_='yuRUbf')
                    if yuRUbf_div:
                        link = yuRUbf_div.find('a')
                        if link and link.get('href'):
                            url = link.get('href')

                    # Fallback: find any link with href
                    if not url:
                        link = container.find('a', href=True)
                        if link:
                            url = link.get('href')

                    if not url or url.startswith('/search'):
                        continue

                    # Extract display URL - look for cite tag
                    cite_elem = container.find('cite')
                    if cite_elem:
                        display_url = cite_elem.get_text(strip=True)
                    else:
                        # Fallback: extract domain from URL
                        try:
                            parsed_url = urllib.parse.urlparse(url)
                            display_url = parsed_url.netloc
                        except:
                            display_url = url

                    # Extract snippet - look for various snippet containers
                    snippet = ""

                    # Strategy 1: VwiC3b class
                    snippet_elem = container.find('div', class_='VwiC3b')
                    if snippet_elem:
                        snippet = snippet_elem.get_text(strip=True)

                    # Strategy 2: Look for div with -webkit-line-clamp style
                    if not snippet:
                        snippet_elem = container.find('div', style=lambda x: x and '-webkit-line-clamp' in x)
                        if snippet_elem:
                            snippet = snippet_elem.get_text(strip=True)

                    # Strategy 3: Look for any text container after title
                    if not snippet:
                        # Find all text divs and get the longest one
                        text_divs = container.find_all('div', recursive=True)
                        for div in text_divs:
                            text = div.get_text(strip=True)
                            if len(text) > len(snippet) and len(text) > 20:
                                snippet = text

                    # Add result
                    result = {
                        'position': position,
                        'title': title,
                        'url': url,
                        'display_url': display_url,
                        'snippet': snippet
                    }

                    results.append(result)
                    position += 1

                    print(f"→ Extracted result {position-1}: {title[:50]}...")

                except Exception as e:
                    print(f"Error parsing individual result: {e}")
                    continue

            print(f"Successfully extracted {len(results)} organic results")

        except Exception as e:
            print(f"Error parsing organic results: {e}")

        return results

    def _extract_total_results(self) -> Optional[str]:
        """Extract total results count from page"""
        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')

            # Look for result stats div
            stats_elem = soup.select_one('div#result-stats')
            if stats_elem:
                stats_text = stats_elem.get_text(strip=True)
                # Extract just the results count part
                # Format is usually "About 1,234,567 results (0.45 seconds)"
                if 'result' in stats_text.lower():
                    return stats_text.split('(')[0].strip()

            return None

        except Exception as e:
            print(f"Error extracting total results: {e}")
            return None

    def scrape_serp(self, query: str, page: int = 1,
                    num_results: int = 10, language: str = "en") -> dict:
        """
        Main method: Scrape Google SERP and return organic results

        Args:
            query: Search query string
            page: Page number (1-based)
            num_results: Number of results per page (10, 20, 30, 50, 100)
            language: Language code (e.g., 'en', 'es')

        Returns:
            dict with 'organic_results', 'total_results', and 'captcha_detected'
        """
        try:
            # Setup driver
            print(f"\nSetting up Chrome driver...")
            self.setup_driver()

            # Build search URL
            search_url = self._build_search_url(query, page, num_results, language)
            print(f"→ Search URL: {search_url}")

            # Add random delay to appear more human-like
            delay = random.uniform(2, 4)
            print(f"→ Waiting {delay:.2f} seconds before request...")
            time.sleep(delay)

            # Navigate to Google search
            print(f"→ Navigating to Google...")
            self.driver.get(search_url)

            # Wait for page to load
            print(f"→ Waiting for results to load...")
            time.sleep(2)

            # Check for CAPTCHA
            print(f"→ Checking for CAPTCHA...")
            if self._check_for_captcha():
                return {
                    'captcha_detected': True,
                    'organic_results': [],
                    'total_results': None
                }

            # Wait for search results to be present
            try:
                wait = WebDriverWait(self.driver, self.wait_timeout)
                wait.until(EC.presence_of_element_located((By.ID, "search")))
            except TimeoutException:
                print("Warning: Timeout waiting for search results container")

            # Parse organic results
            print(f"→ Parsing organic results...")
            organic_results = self._parse_organic_results()

            # Extract total results count
            print(f"→ Extracting total results count...")
            total_results = self._extract_total_results()

            return {
                'captcha_detected': False,
                'organic_results': organic_results,
                'total_results': total_results
            }

        except Exception as e:
            print(f"Error in scrape_serp: {e}")
            raise

        finally:
            # Always cleanup
            self.cleanup()

    def cleanup(self):
        """Close the browser and cleanup"""
        if self.driver:
            print("Closing browser...")
            self.driver.quit()


# Test the automation
if __name__ == "__main__":
    automation = GoogleSerpAutomation()
    try:
        results = automation.scrape_serp("python programming", page=1, num_results=10)

        if results.get('captcha_detected'):
            print("\nCAPTCHA was detected!")
        else:
            print(f"\nSuccess! Found {len(results['organic_results'])} results")
            print(f"Total results: {results.get('total_results')}")

            for result in results['organic_results'][:3]:
                print(f"\n{result['position']}. {result['title']}")
                print(f"   URL: {result['url']}")
                print(f"   Snippet: {result['snippet'][:100]}...")

    except Exception as e:
        print(f"\nError: {e}")

"""
Daily Job Scraper - Tech/AI Focus v3
- Unlimited jobs, max 7 days old, no repeats
- Company name + apply links (hyperlinked titles)
- Two messages: Fintech + AI
"""

import os
import sys
import time
import random
import json
import requests
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

# Groq config - set GROQ_API_KEY environment variable or use .env.local
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Try loading from .env.local if not set
if not GROQ_API_KEY:
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env.local")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    if key == 'GROQ_API_KEY':
                        GROQ_API_KEY = val
                        break
GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile", 
    "qwen/qwen3-32b"
]
MODEL_USAGE = {model: 0 for model in GROQ_MODELS}
LAST_MODEL_SWITCH = None

# Track LLM usage
LLM_CALLS = 0

def categorize_with_llm(title, company, description=""):
    """Use LLM to intelligently categorize a job as FINTECH, AI, or OTHER"""
    global LLM_CALLS, MODEL_USAGE, LAST_MODEL_SWITCH
    
    if not GROQ_API_KEY:
        return categorize_from_text(f"{title} {company} {description[:1000]}")
    
    prompt = f"""Classify this job posting and rate relevance (1-10).

Job Title: {title}
Company: {company}
Description snippet: {description[:800] if description else 'N/A'}

Categories:
- FINTECH: fintech, payments, lending, trading, crypto, blockchain, banking, insurance, wealth, investment, financial services
- AI: AI, ML, LLMs, data engineering, data science, MLOps, computer vision, robotics, NLP, recommendation systems, MLE
- SOFTWARE: software engineering roles - backend, frontend, fullstack, devops, sre, platform, infrastructure, mobile, web
- ADJACENT: jobs at fintech/AI/tech companies but not directly technical (e.g., sales, marketing, HR, operations, customer success at fintech companies)
- OTHER: unrelated to fintech, AI, or software

If the job has any software engineering (backend, frontend, fullstack, devops, sre, platform, infrastructure, mobile, data, etc.), classify as SOFTWARE regardless of company.

Respond with: CATEGORY (relevance_score)
Examples: FINTECH 9, AI 8, SOFTWARE 8, ADJACENT 6, OTHER 2

Respond with only one line like: SOFTWARE 8"""

    try:
        # Select model - switch after 30 requests (rotate through models)
        current_time = time.time()
        if LAST_MODEL_SWITCH and (current_time - LAST_MODEL_SWITCH) < 60:
            # Find model with lowest usage under limit
            model = min(GROQ_MODELS, key=lambda m: MODEL_USAGE[m])
        else:
            # Reset and pick least used
            MODEL_USAGE = {m: 0 for m in GROQ_MODELS}
            model = GROQ_MODELS[0]
            LAST_MODEL_SWITCH = current_time
        
        # Use Groq client
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_completion_tokens=10,
            stop=None
        )
        
        response_text = completion.choices[0].message.content.strip().upper()
        
        # Parse "CATEGORY SCORE" format
        parts = response_text.split()
        if len(parts) >= 2:
            category = parts[0]
            try:
                score = int(parts[1])
            except:
                score = 5
        else:
            category = response_text
            score = 5
        
        valid_categories = ["FINTECH", "AI", "SOFTWARE", "ADJACENT", "OTHER"]
        if category in valid_categories and score >= 6:  # Only keep relevance 6+
            LLM_CALLS += 1
            MODEL_USAGE[model] += 1
            if LLM_CALLS <= 5:
                print(f"  [LLM] {title[:30]}... -> {category} {score}/10 ({model})")
            return category
        
        return "OTHER"  # Low relevance = OTHER
    except Exception as e:
        print(f"  [LLM] Error: {e}")
    
    # Fallback to keyword matching
    return categorize_from_text(f"{title} {company} {description[:1000] if description else ''}")
    
    # Fallback to keyword matching
    return categorize_from_text(f"{title} {company} {description[:1000] if description else ''}")

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
SENT_JOBS_FILE = os.path.join(OUTPUT_DIR, "sent_jobs.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

JOBS = []
SEEN_URLS = set()
SENT_URLS = set()  # Jobs already sent in past

# Load previously sent jobs
def load_sent_jobs():
    global SENT_URLS
    try:
        if os.path.exists(SENT_JOBS_FILE):
            with open(SENT_JOBS_FILE, "r") as f:
                data = json.load(f)
                # Get jobs from last 14 days
                cutoff = datetime.now() - timedelta(days=14)
                for job in data.get("jobs", []):
                    sent_date = datetime.fromisoformat(job.get("date", "2020-01-01"))
                    if sent_date > cutoff:
                        SENT_URLS.add(job.get("url", ""))
                print(f"[CACHE] Loaded {len(SENT_URLS)} recent sent jobs")
    except Exception as e:
        print(f"[CACHE] Error loading: {e}")

def save_sent_jobs(new_jobs):
    """Save new jobs to sent list"""
    try:
        data = {"jobs": [], "last_updated": datetime.now().isoformat()}
        
        # Load existing
        if os.path.exists(SENT_JOBS_FILE):
            try:
                with open(SENT_JOBS_FILE, "r") as f:
                    data = json.load(f)
            except:
                pass
        
        # Add new jobs
        for job in new_jobs:
            data["jobs"].append({
                "url": job["url"],
                "title": job["title"],
                "company": job["company"],
                "date": datetime.now().isoformat()
            })
        
        # Keep all jobs (no time limit)
        cutoff = datetime.now() - timedelta(days=365)
        data["jobs"] = [j for j in data["jobs"] 
                       if datetime.fromisoformat(j.get("date", "2020-01-01")) > cutoff]
        
        with open(SENT_JOBS_FILE, "w") as f:
            json.dump(data, f)
            
        print(f"[CACHE] Saved {len(new_jobs)} new jobs, {len(data['jobs'])} total")
    except Exception as e:
        print(f"[CACHE] Error saving: {e}")

# Tech keywords
TECH_KEYWORDS = [
    'ai', 'machine learning', 'ml', 'deep learning', 'data scientist', 'data engineer',
    'nlp', 'llm', 'large language model', 'gen ai', 'generative ai', 'artificial intelligence',
    'neural', 'model training', 'mlops', 'computer vision', 'robotics', 'autonomous',
    'backend', 'full stack', 'full-stack', 'software engineer', 'sre', 'devops',
    'infrastructure', 'platform', 'foundation', 'founding engineer', 'principal engineer',
    'staff engineer', 'data infrastructure', 'pipeline', 'etl', 'data platform',
    'distributed systems', 'systems engineer', 'cloud', 'aws', 'gcp', 'azure',
    'python', 'golang', 'rust', 'java ', 'c++', 'data', 'analytics', 'bi',
    'search', 'recommendation', 'ranking', 'embedding', 'vector',
    'kubernetes', 'terraform', 'warehouse', 'lakehouse', 'spark', 'flink', 'kafka'
]

EXCLUDE_KEYWORDS = [
    'sales', 'marketing', 'account executive', 'business development', 'revenue',
    'hr ', 'human resources', 'recruiter', 'recruiting', 'people operations',
    'support', 'customer success', 'customer service', 'success manager',
    'content writer', 'copywriter', 'social media', 'community manager',
    'intern', 'internship', 'manager', 'director', 'head of', 'vp ', 'chief', 
    'coordinator', 'specialist', 'designer', 'ux', 'ui '
]

def is_tech_job(title, company):
    text = f"{title} {company}".lower()
    has_tech = any(kw in text for kw in TECH_KEYWORDS)
    has_exclude = any(kw in text for kw in EXCLUDE_KEYWORDS)
    
    if any(kw in text for kw in ['founding engineer', 'principal engineer', 'staff engineer', 
                                   'infrastructure engineer', 'platform engineer', 'data infrastructure',
                                   'backend engineer', 'backend developer']):
        return True
    return has_tech and not has_exclude

def categorize_from_text(text):
    text_lower = text.lower()
    
    fintech_keywords = ['fintech', 'finance', 'payment', 'lending', 'insurance', 'trading', 
                       'crypto', 'blockchain', 'asset', 'wealth', 'investment', 'banking', 'financial']
    
    ai_keywords = ['ai ', 'artificial intelligence', 'machine learning', 'deep learning',
                   'llm', 'large language model', 'gpt', 'gen ai', 'generative ai', 'nlp', 
                   'natural language', 'data engineer', 'data scientist', 'ml engineer', 'mlops',
                   'computer vision', 'robotics', 'autonomous', 'reinforcement learning',
                   'neural', 'embedding', 'vector database', 'model training', 'model serving',
                   'inference', 'pytorch', 'tensorflow', 'recommendation', 'ranking', 'search ',
                   'data pipeline', 'etl', 'data lake', 'data warehouse', 'big data',
                   'spark', 'flink', 'kafka', 'airflow', 'llamaindex', 'langchain', 'rag ']
    
    for kw in fintech_keywords:
        if kw in text_lower:
            return "FINTECH"
    for kw in ai_keywords:
        if kw in text_lower:
            return "AI"
    return "OTHER"

def add_job(title, company, url, source, location="", salary="", apply_link="", posted_date=None):
    """Add job - let LLM filter for relevance instead of keywords"""
    if not url or url in SEEN_URLS:
        return
    if url in SENT_URLS:
        print(f"  [SKIP] Already sent: {title[:40]}")
        return
    # Skip keyword filter - let LLM do relevance filtering instead
    # if not is_tech_job(title, company):
    #     return
    
    SEEN_URLS.add(url)
    JOBS.append({
        "title": title.strip() if title else "Unknown",
        "company": company.strip() if company else "Unknown",
        "url": url.strip(),
        "source": source,
        "location": location.strip() if location else "",
        "salary": salary.strip() if salary else "",
        "apply_link": apply_link.strip() if apply_link else url.strip(),
        "description": "",
        "posted_date": posted_date,
        "category": "OTHER"
    })

def init_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Driver init error: {e}")
        return None

def random_delay(min_sec=0.3, max_sec=1.0):
    time.sleep(random.uniform(min_sec, max_sec))

def parse_relative_date(text):
    """Parse relative date like '2 days ago', '1 week ago'"""
    text = text.lower()
    try:
        if 'hour' in text:
            return datetime.now() - timedelta(hours=int(''.join(filter(str.isdigit, text.split('hour')[0])) or 1))
        elif 'day' in text:
            days = int(''.join(filter(str.isdigit, text.split('day')[0])) or 1)
            return datetime.now() - timedelta(days=days)
        elif 'week' in text:
            weeks = int(''.join(filter(str.isdigit, text.split('week')[0])) or 1)
            return datetime.now() - timedelta(weeks=weeks)
        elif 'month' in text:
            return datetime.now() - timedelta(days=30)
    except:
        pass
    return None

def extract_job_details(driver, url):
    """Visit job page and extract salary, company, apply link, date"""
    try:
        driver.get(url)
        random_delay(1, 2)
        
        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        page_text = soup.get_text()
        page_lower = page_text.lower()
        
        # Extract salary
        salary = ""
        salary_range = re.findall(r'\$[\d]+k\s*[-–]\s*\$[\d]+k', page_lower)
        if salary_range:
            salary = salary_range[0].replace('$', '').replace('k', 'K')
        if not salary:
            salary_full = re.findall(r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?', page_text)
            for s in salary_full:
                if ',' in s and len(s) > 5:
                    salary = s.replace('$', '').replace(',', '')
                    break
        
        # Extract company name - try multiple methods
        company = "Unknown"
        
        # Method 1: Extract from URL (works for YC/Wellfound)
        match = re.search(r'/companies/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
        
        # Method 2: Look for company in page text
        if company == "Unknown":
            # Try finding company name near job title or in header
            company_elem = soup.find(['a', 'span', 'div', 'p'], string=re.compile(r'^[A-Z][a-zA-Z\s]{2,40}$'))
            if company_elem:
                txt = company_elem.get_text(strip=True)
                if txt and len(txt) > 2 and len(txt) < 50:
                    company = txt
        
        # Method 3: Look for company in specific patterns
        if company == "Unknown":
            company_link = soup.find('a', href=re.compile(r'/company/'))
            if company_link:
                company = company_link.get_text(strip=True)
                if not company:
                    # Get from href
                    href = company_link.get('href', '')
                    match = re.search(r'/company/([^/]+)', href)
                    if match:
                        company = match.group(1).replace('-', ' ').title()
        
        # Extract apply link
        apply_link = url  # Default to job URL
        
        # Look for apply button/link
        # Look for apply button/link - use string instead of text
        apply_buttons = soup.find_all('a', href=True, string=lambda x: x and 'apply' in x.lower() if x else False)
        if apply_buttons:
            apply_link = apply_buttons[0].get('href', url)
            if apply_link and not apply_link.startswith('http'):
                apply_link = urljoin(url, apply_link)
        
        # Look for external apply links
        if apply_link == url:
            external_apply = soup.find_all('a', href=lambda x: x and ('apply' in x.lower() or 'lever' in x or 'greenhouse' in x or 'applytojob' in x) if x else False)
            for btn in external_apply[:1]:
                href = btn.get('href', '')
                if href and 'http' in href:
                    apply_link = href
                    break
        
        # Extract posted date
        posted_date = None
        date_patterns = [
            re.findall(r'posted\s*(\d+)\s*(hour|day|week|month)', page_lower),
            re.findall(r'(\d+)\s*(hour|day|week|month)\s*ago', page_lower),
        ]
        for pattern in date_patterns:
            if pattern:
                try:
                    num = int(pattern[0][0])
                    unit = pattern[0][1]
                    if 'hour' in unit:
                        posted_date = datetime.now() - timedelta(hours=num)
                    elif 'day' in unit:
                        posted_date = datetime.now() - timedelta(days=num)
                    elif 'week' in unit:
                        posted_date = datetime.now() - timedelta(weeks=num)
                    break
                except:
                    pass
        
        description = page_text[:3000]
        
        return salary, company, apply_link, description, posted_date
        
    except Exception as e:
        return "", "Unknown", url, "", None

def scrape_wellfound(driver):
    print("[wellfound] Scraping...")
    try:
        driver.get("https://wellfound.com/jobs")
        random_delay(2, 4)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        links = soup.find_all("a", href=lambda x: x and "/jobs/" in x and "/company/" not in x and "role" not in x)
        
        for link in links[:200]:  # Increased from 150
            title = link.get_text(strip=True)
            if title and len(title) > 5:
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://wellfound.com" + href
                add_job(title, "", href, "Wellfound")
        
        print(f"[wellfound] Found {len(links)} jobs")
        
    except Exception as e:
        print(f"[wellfound] Error: {e}")

def scrape_yn_category(driver, category, url_suffix):
    try:
        driver.get(f"https://www.ycombinator.com/jobs/role/{url_suffix}")
        random_delay(2, 3)
        
        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        job_links = soup.find_all("a", href=re.compile(r'/companies/[^/]+/jobs/\w+'))
        
        for link in job_links[:100]:  # Increased from 60
            title = link.get_text(strip=True)
            if title and len(title) > 3:
                href = link.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.ycombinator.com" + href
                add_job(title, "", href, "YC Jobs")
        
        return len(job_links)
    except Exception as e:
        return 0

def scrape_yc(driver):
    print("[ycombinator] Scraping...")
    
    categories = [
        ("engineering", "software-engineer"),
        ("product", "product-manager"),
        ("backend", "backend"),
        ("data", "data-engineer"),
        ("infrastructure", "infrastructure"),
        ("ml", "machine-learning"),
    ]
    
    total = 0
    for name, suffix in categories:
        count = scrape_yn_category(driver, name, suffix)
        total += count
    
    print(f"[ycombinator] Found {total} jobs")

def scrape_techstars(driver):
    print("[techstars] Scraping...")
    try:
        driver.get("https://www.techstars.com/companies/hiring")
        random_delay(3, 5)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        links = soup.find_all("a", href=lambda x: x and ("careers" in x.lower() or "jobs" in x.lower()))
        
        for link in links[:80]:
            title = link.get_text(strip=True)
            if title and len(title) > 3:
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://www.techstars.com" + href
                add_job(title, "", href, "Techstars")
        
        print(f"[techstars] Found {len(links)} links")
        
    except Exception as e:
        print(f"[techstars] Error: {e}")

def second_pass_details(driver, jobs_list, max_visits=80):
    """Visit job pages to extract all details"""
    print(f"\n[detail-pass] Visiting up to {max_visits} job pages...")
    
    cutoff_date = datetime.now() - timedelta(days=365)  # No time limit - get all jobs
    ai_count = 0
    fintech_count = 0
    software_count = 0
    adjacent_count = 0
    skipped_old = 0
    
    for i, job in enumerate(jobs_list[:max_visits]):
        try:
            salary, company, apply_link, description, posted_date = extract_job_details(driver, job['url'])
            
            if salary:
                job['salary'] = salary
            if company and company != "Unknown":
                job['company'] = company
            if apply_link:
                job['apply_link'] = apply_link
            if description:
                job['description'] = description
            # No date filtering - get all jobs
            # Recategorize using LLM - always call even without description
            category = categorize_with_llm(job.get('title', ''), company, description or "")
            job['category'] = category
            
            # Count categories
            if category == "AI":
                ai_count += 1
            elif category == "FINTECH":
                fintech_count += 1
            elif category == "SOFTWARE":
                software_count += 1
            elif category == "ADJACENT":
                adjacent_count += 1
            
            if salary and i < 20:
                print(f"  [{i+1}] {job['title'][:30]} @ {company[:20]} [{job['category']}] -> {salary}")
            
            random_delay(0.2, 0.6)
            
        except Exception as e:
            job['category'] = "OTHER"
            continue
    
    print(f"[detail-pass] Categorized: {ai_count} AI, {fintech_count} Fintech, {software_count} Software, {adjacent_count} Adjacent")
    return ai_count, fintech_count, software_count, adjacent_count

def format_jobs_by_category(jobs, category, max_count=999):  # No limit
    categorized = [j for j in jobs if j.get('category') == category]
    jobs_to_send = categorized[:max_count]
    
    if not jobs_to_send:
        return None, 0
    
    emoji = "🏦" if category == "FINTECH" else ("🤖" if category == "AI" else ("💻" if category == "SOFTWARE" else "🔗"))
    output = f"{emoji} *{category} Tech Jobs* — {datetime.now().strftime('%b %d')}\n"
    
    if category == "FINTECH":
        output += "_Fintech, Payments, Crypto, Banking, Financial Services_\n\n"
    elif category == "AI":
        output += "_AI, ML, Data Engineering, LLMs, GenAI_\n\n"
    elif category == "SOFTWARE":
        output += "_Backend, Frontend, Fullstack, DevOps, Platform, Infrastructure_\n\n"
    else:
        output += "_Non-technical roles at tech companies_\n\n"
    
    for i, job in enumerate(jobs_to_send, 1):
        # Hyperlinked title with apply link
        apply_url = job.get('apply_link', job['url'])
        output += f"{i}. [{job['title']}]({apply_url})"
        
        if job['company'] and job['company'] != "Unknown":
            output += f" @ *{job['company']}*"
        output += "\n"
        
        if job.get('salary'):
            output += f"   💰 {job['salary']}\n"
        
        output += f"   📍 {job['source']}\n\n"
    
    return output, len(categorized)

def save_output():
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(OUTPUT_DIR, f"jobs-{today}.md")
    
    fintech = [j for j in JOBS if j.get('category') == "FINTECH"]
    ai = [j for j in JOBS if j.get('category') == "AI"]
    software = [j for j in JOBS if j.get('category') == "SOFTWARE"]
    adjacent = [j for j in JOBS if j.get('category') == "ADJACENT"]
    other = [j for j in JOBS if j.get('category') not in ["FINTECH", "AI", "SOFTWARE", "ADJACENT"]]
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Job Postings — {today}\n")
        f.write(f"_All jobs - LLM filtered for relevance/adjacency_\n\n")
        f.write(f"Total: {len(JOBS)} jobs\n")
        f.write(f"- Fintech: {len(fintech)}\n")
        f.write(f"- AI/ML: {len(ai)}\n")
        f.write(f"- Software: {len(software)}\n")
        f.write(f"- Adjacent: {len(adjacent)}\n")
        f.write(f"- Other: {len(other)}\n\n")
        
        f.write("## Fintech Jobs\n\n")
        for job in fintech[:50]:
            f.write(f"### [{job['title']}]({job.get('apply_link', job['url'])})\n")
            f.write(f"- **Company:** {job['company']}\n")
            f.write(f"- **Salary:** {job.get('salary') or 'N/A'}\n")
            f.write(f"- **Source:** {job['source']}\n\n")
        
        f.write("## AI/ML Jobs\n\n")
        for job in ai[:50]:
            f.write(f"### [{job['title']}]({job.get('apply_link', job['url'])})\n")
            f.write(f"- **Company:** {job['company']}\n")
            f.write(f"- **Salary:** {job.get('salary') or 'N/A'}\n")
            f.write(f"- **Source:** {job['source']}\n\n")
        
        f.write("## Software Engineering Jobs\n\n")
        for job in software[:50]:
            f.write(f"### [{job['title']}]({job.get('apply_link', job['url'])})\n")
            f.write(f"- **Company:** {job['company']}\n")
            f.write(f"- **Salary:** {job.get('salary') or 'N/A'}\n")
            f.write(f"- **Source:** {job['source']}\n\n")
        
        f.write("## Adjacent Jobs (Non-technical roles at tech companies)\n\n")
        for job in adjacent[:30]:
            f.write(f"### [{job['title']}]({job.get('apply_link', job['url'])})\n")
            f.write(f"- **Company:** {job['company']}\n")
            f.write(f"- **Salary:** {job.get('salary') or 'N/A'}\n")
            f.write(f"- **Source:** {job['source']}\n\n")
    
    # Save to sent jobs
    save_sent_jobs(JOBS)
    
    return filepath, len(fintech), len(ai), len(software), len(adjacent)

def main():
    print(f"\n[START] Job scrape at {datetime.now()}\n")
    
    # Load previously sent jobs
    load_sent_jobs()
    
    driver = init_driver()
    if not driver:
        print("Failed to initialize driver")
        return None, None
    
    try:
        scrape_wellfound(driver)
        scrape_yc(driver)
        scrape_techstars(driver)
        
        print(f"\n[FILTER] After tech filtering: {len(JOBS)} jobs")
        
        # Second pass: extract all details - process all jobs now
        second_pass_details(driver, JOBS, max_visits=500)
        
    finally:
        driver.quit()
    
    filepath, fintech_count, ai_count, software_count, adjacent_count = save_output()
    
    print(f"\n[COMPLETE] Found {len(JOBS)} jobs")
    print(f"[SUMMARY] Fintech: {fintech_count}, AI: {ai_count}, Software: {software_count}, Adjacent: {adjacent_count}")
    print(f"[LLM] Used LLM for {LLM_CALLS} categorizations")
    print(f"[FILE] Saved to: {filepath}")
    
    # Format outputs
    fintech_result = format_jobs_by_category(JOBS, "FINTECH")
    ai_result = format_jobs_by_category(JOBS, "AI")
    
    fintech_msg = fintech_result[0] if fintech_result else None
    ai_msg = ai_result[0] if ai_result else None
    
    if not fintech_msg:
        fintech_msg = "🏦 *FINTECH Tech Jobs* — No new fintech jobs today"
    if not ai_msg:
        ai_msg = "🤖 *AI/ML Jobs* — No new AI/ML jobs today"
    
    return fintech_msg, ai_msg

if __name__ == "__main__":
    main()
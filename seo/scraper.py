import socket
import urllib.parse
import ipaddress
import requests
import validators
from bs4 import BeautifulSoup
import copy

class ScrapeError(Exception):
    """Custom exception raised for scraper failures."""
    pass

def is_ssrf_safe(url: str) -> bool:
    """
    Checks if a URL resolves to a private, loopback, or link-local IP range (SSRF guard).
    Returns True if the address is safe (public), False otherwise.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Resolve all IP addresses for the hostname
        addr_info = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            # Convert to IP address object (handles IPv4 and IPv6)
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                return False
        return True
    except socket.gaierror:
        # Host name resolution failed
        return False
    except Exception:
        return False

def scrape_page(url: str) -> dict:
    """
    Validates the URL, checks for SSRF, fetches HTML (up to 5MB, 10s timeout),
    and parses SEO attributes from the page.
    Best-effort fetches robots.txt and sitemap.xml from the domain root.
    Raises ScrapeError for invalid or unreachable inputs.
    """
    # 1. URL Validation
    is_valid = validators.url(url)
    if is_valid is not True:
        raise ScrapeError("Invalid URL format. Please provide a valid absolute URL (e.g., https://example.com).")
        
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ScrapeError("Invalid URL scheme. Only HTTP and HTTPS are supported.")
        
    # 2. SSRF check
    if not is_ssrf_safe(url):
        raise ScrapeError("Blocked URL: access to private/local network ranges is prohibited.")
        
    headers = {
        "User-Agent": "SEOAuditorTelegramBot/1.0 (+https://t.me/SEOAuditorRealTimeBot)"
    }
    
    # 3. Fetch HTTP Content
    try:
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        response.raise_for_status()
        
        # Check size via Content-Length header first
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > 5 * 1024 * 1024:
                    raise ScrapeError("The page content exceeds the maximum size limit of 5MB.")
            except ValueError:
                pass
                
        # Read body in chunks to enforce size limit
        content = bytearray()
        max_size = 5 * 1024 * 1024
        for chunk in response.iter_content(chunk_size=4096):
            content.extend(chunk)
            if len(content) > max_size:
                raise ScrapeError("The page content exceeds the maximum size limit of 5MB.")
                
        html_content = content.decode(response.encoding or 'utf-8', errors='replace')
    except requests.exceptions.Timeout:
        raise ScrapeError("Request timed out. The server took more than 10 seconds to respond.")
    except requests.exceptions.HTTPError as e:
        raise ScrapeError(f"HTTP error {e.response.status_code}: {e.response.reason}")
    except requests.exceptions.RequestException as e:
        raise ScrapeError(f"Failed to fetch URL: {str(e)}")
    except ScrapeError:
        raise
    except Exception as e:
        raise ScrapeError(f"An unexpected error occurred during scrape: {str(e)}")
        
    # 4. Parse content using BeautifulSoup
    try:
        soup = BeautifulSoup(html_content, 'lxml')
    except Exception:
        # Fallback to python standard html parser if lxml is unavailable
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            raise ScrapeError(f"Failed to parse HTML document: {str(e)}")
            
    # Extraction 4a: Title
    title_tag = soup.find('title')
    title = title_tag.get_text().strip() if title_tag else None
    
    # Extraction 4b: Meta Description
    meta_desc_tag = soup.find('meta', attrs={'name': lambda x: x and x.lower() == 'description'})
    meta_description = meta_desc_tag.get('content', '').strip() if meta_desc_tag else None
    
    # Extraction 4c: Headings hierarchy
    headings = []
    for h_tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        headings.append({
            'tag': h_tag.name,
            'text': h_tag.get_text().strip()
        })
        
    # Extraction 4d: Images & Alt tags
    images = []
    for img in soup.find_all('img'):
        images.append({
            'src': img.get('src'),
            'has_alt': 'alt' in img.attrs,
            'alt_value': img.get('alt', '').strip()
        })
        
    # Extraction 4e: Canonical Link
    canonical_tag = soup.find('link', rel='canonical')
    canonical = canonical_tag.get('href', '').strip() if canonical_tag else None
    
    # Extraction 4f: Viewport Metadata
    viewport_tag = soup.find('meta', attrs={'name': lambda x: x and x.lower() == 'viewport'})
    viewport = viewport_tag.get('content', '').strip() if viewport_tag else None
    
    # Extraction 4g: Open Graph & Twitter Cards
    og_tags = {}
    twitter_tags = {}
    for meta in soup.find_all('meta'):
        prop = meta.get('property', '')
        name = meta.get('name', '')
        val = meta.get('content', '')
        
        if prop.startswith('og:'):
            og_tags[prop] = val
        elif name.startswith('og:'):
            og_tags[name] = val
        elif name.startswith('twitter:'):
            twitter_tags[name] = val
        elif prop.startswith('twitter:'):
            twitter_tags[prop] = val
            
    # Extraction 4h: JSON-LD block contents
    json_ld = []
    for script in soup.find_all('script', type='application/ld+json'):
        if script.string:
            json_ld.append(script.string.strip())
            
    # Extraction 4i: Visible Word Count (excluding code, styles, scripts)
    word_count = 0
    body = soup.find('body')
    if body:
        try:
            body_clone = copy.deepcopy(body)
            # Remove formatting/non-visible tags
            for elem in body_clone(['script', 'style', 'noscript', 'iframe', 'svg', 'canvas', 'select', 'textarea']):
                elem.decompose()
            words = body_clone.get_text(separator=' ').split()
            word_count = len(words)
        except Exception:
            word_count = 0
            
    # Extraction 4j: Mixed Content Assets list (for HTTPS check later)
    assets = []
    for tag in soup.find_all(['img', 'script', 'link']):
        src = tag.get('src') or tag.get('href')
        if src:
            assets.append(src.strip())
            
    # 5. Best-effort fetch of robots.txt and sitemap.xml at domain root
    domain_root = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{domain_root}/robots.txt"
    sitemap_url = f"{domain_root}/sitemap.xml"
    
    robots_txt = None
    sitemap_xml = None
    
    try:
        if is_ssrf_safe(robots_url):
            r_resp = requests.get(robots_url, headers=headers, timeout=5)
            if r_resp.status_code == 200:
                robots_txt = r_resp.text
    except Exception:
        pass
        
    try:
        if is_ssrf_safe(sitemap_url):
            s_resp = requests.get(sitemap_url, headers=headers, timeout=5)
            if s_resp.status_code == 200:
                sitemap_xml = s_resp.text
    except Exception:
        pass
        
    return {
        "url": url,
        "scheme": parsed.scheme,
        "title": title,
        "meta_description": meta_description,
        "headings": headings,
        "images": images,
        "canonical": canonical,
        "viewport": viewport,
        "og_tags": og_tags,
        "twitter_tags": twitter_tags,
        "json_ld": json_ld,
        "word_count": word_count,
        "robots_txt": robots_txt,
        "sitemap_xml": sitemap_xml,
        "assets": assets
    }

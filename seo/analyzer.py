import json
import urllib.parse
import validators

def is_generic_title(title: str) -> bool:
    """Helper to detect if the title tag is generic (e.g. 'Home', 'Welcome')."""
    title_lower = title.lower().strip()
    generic_words = {'home', 'index', 'welcome', 'page', 'website', 'untitled', 'default', 'new page', 'my site'}
    for word in generic_words:
        if word == title_lower or title_lower.startswith(word + ' -') or title_lower.endswith('- ' + word):
            return True
    return False

def check_title(title: str) -> dict:
    """Evaluates the title tag (10 points max)."""
    check_name = "Title Tag"
    max_pts = 10
    
    if not title:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "The <title> tag is missing. Search engines rely on titles to index your pages; add a unique title tag to the page head."
        }
        
    cleaned_title = title.strip()
    if not cleaned_title:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "The <title> tag is empty. Add descriptive text to your title tag to describe the page content."
        }
        
    if is_generic_title(cleaned_title):
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 5,
            "points_possible": max_pts,
            "message": f"The title tag '{cleaned_title}' is too generic. Replace generic labels with unique, descriptive keywords relevant to your page."
        }
        
    title_len = len(cleaned_title)
    if title_len < 50:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 7,
            "points_possible": max_pts,
            "message": f"The title tag is too short ({title_len} characters). Expand your title to 50-60 characters with relevant keywords to maximize visibility."
        }
    elif title_len > 60:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 7,
            "points_possible": max_pts,
            "message": f"The title tag is too long ({title_len} characters). Truncate your title to 50-60 characters so it doesn't get clipped in search results."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": f"The title tag is present, descriptive, and has an optimal length ({title_len} characters)."
    }

def check_meta_description(meta_desc: str, title: str) -> dict:
    """Evaluates the meta description (10 points max)."""
    check_name = "Meta Description"
    max_pts = 10
    
    if not meta_desc:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "Meta description is missing. Add a <meta name='description'> tag to summarize your page and encourage user clicks."
        }
        
    cleaned_desc = meta_desc.strip()
    if not cleaned_desc:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "Meta description is empty. Write a 150-160 character summary describing your page to display in search snippet results."
        }
        
    if title and cleaned_desc == title.strip():
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 3,
            "points_possible": max_pts,
            "message": "Meta description is identical to the title tag. Write a unique description that expands on the page title."
        }
        
    desc_len = len(cleaned_desc)
    if desc_len < 150:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 7,
            "points_possible": max_pts,
            "message": f"Meta description is too short ({desc_len} characters). Expand your description to 150-160 characters to fully describe the content."
        }
    elif desc_len > 160:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 7,
            "points_possible": max_pts,
            "message": f"Meta description is too long ({desc_len} characters). Shorten it to 150-160 characters to prevent truncation in search result snippets."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": f"Meta description is present, unique, and has an optimal length ({desc_len} characters)."
    }

def check_headings(headings: list) -> dict:
    """Evaluates heading levels and hierarchy (10 points max)."""
    check_name = "Heading Structure"
    max_pts = 10
    
    h1_headings = [h for h in headings if h['tag'] == 'h1']
    h1_count = len(h1_headings)
    
    if h1_count == 0:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "No H1 tag found. Every page must contain exactly one <h1> tag serving as the main headline for structure."
        }
        
    if h1_count > 1:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 5,
            "points_possible": max_pts,
            "message": f"Multiple H1 tags found ({h1_count}). Use exactly one <h1> tag as the main title, and use <h2>-<h6> subheadings."
        }
        
    h1_text = h1_headings[0]['text'].strip()
    if not h1_text:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 2,
            "points_possible": max_pts,
            "message": "The H1 tag is empty. Add descriptive title text inside the <h1> tag to define the primary subject of the page."
        }
        
    # Check nesting order (e.g. no jumps like h1 -> h3 without an h2)
    nesting_issues = False
    prev_level = 0
    for h in headings:
        level = int(h['tag'][1])
        if prev_level > 0 and level > prev_level + 1:
            nesting_issues = True
            break
        prev_level = level
        
    if nesting_issues:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 8,
            "points_possible": max_pts,
            "message": "Heading levels skip hierarchy (e.g., H2 to H4 skipping H3). Structure headings sequentially to improve accessibility."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": f"Heading structure is healthy, with exactly one non-empty <h1> tag ('{h1_text}') and logical hierarchy nesting."
    }

def check_images(images: list) -> dict:
    """Evaluates image alt tags presence (10 points max)."""
    check_name = "Image Alt Attributes"
    max_pts = 10
    
    total_imgs = len(images)
    if total_imgs == 0:
        return {
            "check": check_name,
            "status": "pass",
            "points_earned": max_pts,
            "points_possible": max_pts,
            "message": "No images detected on the page. Alt attributes are not required."
        }
        
    alt_imgs = sum(1 for img in images if img['has_alt'] and img['alt_value'])
    pct = (alt_imgs / total_imgs) * 100
    points_earned = round((alt_imgs / total_imgs) * max_pts)
    
    if pct == 100:
        return {
            "check": check_name,
            "status": "pass",
            "points_earned": max_pts,
            "points_possible": max_pts,
            "message": f"All {total_imgs} images have descriptive, non-empty alt attributes."
        }
    elif pct >= 50:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": points_earned,
            "points_possible": max_pts,
            "message": f"Only {alt_imgs} of {total_imgs} images ({pct:.1f}%) have alt attributes. Add descriptive alt text to all images to help visually impaired users and image search crawlers."
        }
        
    return {
        "check": check_name,
        "status": "fail",
        "points_earned": points_earned,
        "points_possible": max_pts,
        "message": f"Critical: only {alt_imgs} of {total_imgs} images ({pct:.1f}%) have alt attributes. The majority of images are missing alt texts, which hurts accessibility and image indexing."
    }

def check_canonical(canonical: str) -> dict:
    """Evaluates canonical link (5 points max)."""
    check_name = "Canonical Tag"
    max_pts = 5
    
    if not canonical:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "Canonical link tag is missing. Add a <link rel='canonical' href='...'> to prevent duplicate content indexing."
        }
        
    is_valid = validators.url(canonical)
    if is_valid is not True:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 2,
            "points_possible": max_pts,
            "message": f"Canonical URL '{canonical}' is present but is not a valid absolute URL. Make sure it contains the scheme and domain name."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": f"Canonical link is present and points to a valid absolute URL ('{canonical}')."
    }

def check_open_graph_twitter(og_tags: dict, twitter_tags: dict) -> dict:
    """Evaluates open graph and twitter card headers (10 points max)."""
    check_name = "Social Sharing Meta Tags"
    max_pts = 10
    
    required_tags = {
        "og:title": og_tags.get("og:title") or og_tags.get("og:title") or twitter_tags.get("og:title"),
        "og:description": og_tags.get("og:description") or twitter_tags.get("og:description"),
        "og:image": og_tags.get("og:image") or twitter_tags.get("og:image"),
        "twitter:card": twitter_tags.get("twitter:card") or og_tags.get("twitter:card")
    }
    
    missing = [k for k, v in required_tags.items() if not v]
    missing_count = len(missing)
    present_count = 4 - missing_count
    
    # Each tag is worth 2.5 points (integer conversion)
    pts = int(present_count * 2.5)
    
    if missing_count == 0:
        return {
            "check": check_name,
            "status": "pass",
            "points_earned": max_pts,
            "points_possible": max_pts,
            "message": "Social sharing tags are fully configured. Essential Open Graph (og:title, og:description, og:image) and Twitter cards (twitter:card) tags are present."
        }
    elif present_count > 0:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": pts,
            "points_possible": max_pts,
            "message": f"Social metadata is partially configured. Missing tags: {', '.join(missing)}. Configure these meta tags to enable rich previews on social media sites."
        }
        
    return {
        "check": check_name,
        "status": "fail",
        "points_earned": 0,
        "points_possible": max_pts,
        "message": "All essential social sharing tags are missing (og:title, og:description, og:image, twitter:card). Add these meta tags to control how your page previews on social networks."
    }

def check_structured_data(json_ld_blocks: list) -> dict:
    """Evaluates JSON-LD structured data (10 points max)."""
    check_name = "Structured Data (Schema.org)"
    max_pts = 10
    
    if not json_ld_blocks:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "Structured data is missing. Add <script type='application/ld+json'> markup to enable search rich snippets and help bots understand content."
        }
        
    has_errors = False
    for block in json_ld_blocks:
        try:
            json.loads(block)
        except json.JSONDecodeError:
            has_errors = True
            break
            
    if has_errors:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 3,
            "points_possible": max_pts,
            "message": "Structured data block was found, but it contains invalid JSON syntax. Validate and format your JSON-LD block markup."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": f"Valid structured data ({len(json_ld_blocks)} JSON-LD blocks) was found and parsed successfully."
    }

def check_https_mixed_content(scheme: str, assets: list) -> dict:
    """Evaluates HTTPS status and mixed-content assets (5 points max)."""
    check_name = "HTTPS & Mixed Content"
    max_pts = 5
    
    if scheme != "https":
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "The website is not served over HTTPS. Install an SSL certificate and redirect HTTP traffic to secure search users and rankings."
        }
        
    mixed_content = [asset for asset in assets if asset.startswith("http://")]
    mixed_count = len(mixed_content)
    
    if mixed_count > 0:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 3,
            "points_possible": max_pts,
            "message": f"The page is served securely over HTTPS, but {mixed_count} page assets (scripts, images, or stylesheets) are loaded insecurely via HTTP. Resolve this mixed content by changing source links to HTTPS."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": "The site is served over HTTPS and no insecure HTTP mixed content resources were detected."
    }

def check_viewport(viewport: str) -> dict:
    """Evaluates mobile viewport meta tag (5 points max)."""
    check_name = "Mobile Viewport"
    max_pts = 5
    
    if not viewport:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "Viewport meta tag is missing. Add <meta name='viewport' content='width=device-width, initial-scale=1.0'> to enable mobile responsiveness."
        }
        
    cleaned_viewport = viewport.lower()
    is_sane = "width=device-width" in cleaned_viewport or "initial-scale" in cleaned_viewport
    
    if not is_sane:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 2,
            "points_possible": max_pts,
            "message": f"Viewport meta tag is present ('{viewport}'), but not configured for standard responsive design. Ensure it includes 'width=device-width, initial-scale=1.0'."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": "Mobile viewport meta tag is present and configured correctly."
    }

def check_robots_sitemap(robots_txt: str, sitemap_xml: str) -> dict:
    """Evaluates robots.txt and sitemap.xml presence and contents (10 points max)."""
    check_name = "robots.txt & sitemap.xml"
    max_pts = 10
    
    has_robots = robots_txt is not None
    has_sitemap = sitemap_xml is not None
    
    if not has_robots and not has_sitemap:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 0,
            "points_possible": max_pts,
            "message": "Both robots.txt and sitemap.xml are missing from the domain root. Add a robots.txt to instruct crawlers and a sitemap.xml to list index URLs."
        }
        
    blocks_all = False
    if has_robots:
        # Normalize and scan lines
        lines = [line.strip().lower() for line in robots_txt.split('\n') if line.strip()]
        is_user_agent_all = False
        for line in lines:
            if line.startswith("user-agent:"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    ua = parts[1].strip()
                    is_user_agent_all = (ua == "*")
            elif line.startswith("disallow:") and is_user_agent_all:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    path = parts[1].strip()
                    if path == "/":
                        blocks_all = True
                        break
                        
    if blocks_all:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 2,
            "points_possible": max_pts,
            "message": "robots.txt is present but contains a 'Disallow: /' block rule for all user agents, preventing search crawlers from indexing your site."
        }
        
    if not has_robots:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 5,
            "points_possible": max_pts,
            "message": "robots.txt is missing from the domain root. Create a robots.txt file to guide search bots on which pages to index or skip."
        }
        
    if not has_sitemap:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 5,
            "points_possible": max_pts,
            "message": "sitemap.xml is missing from the domain root. Create a sitemap.xml to help search engines discover and index your page URLs faster."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": "Both robots.txt and sitemap.xml are present and correctly configured at the domain root."
    }

def check_content_length(word_count: int) -> dict:
    """Evaluates page visible body word count (10 points max)."""
    check_name = "Content Length"
    max_pts = 10
    
    if word_count < 100:
        return {
            "check": check_name,
            "status": "fail",
            "points_earned": 2,
            "points_possible": max_pts,
            "message": f"Critical: very thin content detected ({word_count} words). Pages with fewer than 100 words are flagged as low-value/thin content by search engines. Expand the copy."
        }
    elif word_count < 300:
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 6,
            "points_possible": max_pts,
            "message": f"Thin page content ({word_count} words). Aim for a minimum of 300 words of high-quality copy to provide depth and improve search visibility."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": f"Satisfactory word count ({word_count} words), providing sufficient depth to satisfy search intent and avoid thin content penalties."
    }

def check_url_structure(url: str) -> dict:
    """Evaluates URL structure, parameters and length (5 points max)."""
    check_name = "URL Structure"
    max_pts = 5
    
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qsl(parsed.query)
        param_names = [name.lower() for name, _ in query_params]
    except Exception:
        query_params = []
        param_names = []
        
    session_params = {'sid', 'jsessionid', 'phpsessid', 'sessid', 'session_id', 'token'}
    has_session_id = any(p in session_params for p in param_names)
    
    reasons = []
    if len(url) > 100:
        reasons.append("is excessively long (exceeds 100 characters)")
    if len(query_params) > 3:
        reasons.append(f"has too many query parameters ({len(query_params)} parameters found)")
    if has_session_id:
        reasons.append("contains session identifier query parameters")
        
    if reasons:
        reasons_msg = ", and it ".join(reasons)
        return {
            "check": check_name,
            "status": "warning",
            "points_earned": 2,
            "points_possible": max_pts,
            "message": f"URL structure could be optimized: it {reasons_msg}. Use short, clean, descriptive URLs without tracking session IDs."
        }
        
    return {
        "check": check_name,
        "status": "pass",
        "points_earned": max_pts,
        "points_possible": max_pts,
        "message": "URL structure is clean, concise, and structured correctly."
    }

def analyze_seo(scrape_data: dict) -> dict:
    """
    Evaluates scraped SEO data against all scoring checklist rules.
    Returns score (0-100), grade (A-F), and breakdown of checks.
    """
    breakdown = []
    
    # Run all 12 checks
    breakdown.append(check_title(scrape_data.get("title")))
    breakdown.append(check_meta_description(scrape_data.get("meta_description"), scrape_data.get("title")))
    breakdown.append(check_headings(scrape_data.get("headings", [])))
    breakdown.append(check_images(scrape_data.get("images", [])))
    breakdown.append(check_canonical(scrape_data.get("canonical")))
    breakdown.append(check_open_graph_twitter(scrape_data.get("og_tags", {}), scrape_data.get("twitter_tags", {})))
    breakdown.append(check_structured_data(scrape_data.get("json_ld", [])))
    breakdown.append(check_https_mixed_content(scrape_data.get("scheme", "http"), scrape_data.get("assets", [])))
    breakdown.append(check_viewport(scrape_data.get("viewport")))
    breakdown.append(check_robots_sitemap(scrape_data.get("robots_txt"), scrape_data.get("sitemap_xml")))
    breakdown.append(check_content_length(scrape_data.get("word_count", 0)))
    breakdown.append(check_url_structure(scrape_data.get("url", "")))
    
    # Calculate totals
    total_earned = sum(item["points_earned"] for item in breakdown)
    total_possible = sum(item["points_possible"] for item in breakdown)
    
    # Normalize score out of 100
    if total_possible > 0:
        score = int(round((total_earned / total_possible) * 100))
    else:
        score = 0
        
    # Grade bands: 90–100 A, 75–89 B, 60–74 C, 40–59 D, <40 F
    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"
        
    return {
        "score": score,
        "grade": grade,
        "breakdown": breakdown
    }

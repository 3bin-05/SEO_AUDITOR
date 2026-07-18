def format_report(url: str, analysis_result: dict) -> list[str]:
    """
    Formats the SEO analysis result dictionary into a list of Telegram-Markdown strings.
    If the content length of the breakdown exceeds Telegram's 4096-character limit,
    it gracefully splits the output into multiple sequential messages (using a 4000 char threshold).
    """
    score = analysis_result.get("score", 0)
    grade = analysis_result.get("grade", "F")
    breakdown = analysis_result.get("breakdown", [])
    
    # 1. Group checks by status
    fails = []
    warnings = []
    passes = []
    
    for item in breakdown:
        status = item.get("status")
        if status == "fail":
            fails.append(item)
        elif status == "warning":
            warnings.append(item)
        else:
            passes.append(item)
            
    # 2. Build lines with length guard
    messages = []
    current_chunk = []
    
    def add_line(line: str):
        nonlocal current_chunk
        # Calculate current chunk length (including join newlines)
        current_len = sum(len(l) for l in current_chunk) + len(current_chunk)
        if current_len + len(line) > 4000:
            if current_chunk:
                messages.append("\n".join(current_chunk))
            current_chunk = [line]
        else:
            current_chunk.append(line)
            
    # Report Header
    add_line("📊 *SEO AUDIT REPORT*")
    add_line(f"🌐 *URL*: {url}")
    add_line(f"⭐️ *Score*: {score}/100 (*Grade: {grade}*)")
    add_line("-" * 30 + "\n")
    
    # Fails Section
    if fails:
        add_line("❌ *FAILS*")
        for item in fails:
            check_title = item.get("check", "Unknown Check")
            earned = item.get("points_earned", 0)
            possible = item.get("points_possible", 0)
            msg = item.get("message", "")
            # Sanitize markdown characters in text to avoid rendering issues
            msg = msg.replace("_", "\\_").replace("*", "\\*")
            add_line(f"• *{check_title}* ({earned}/{possible} pts)")
            add_line(f"  {msg}\n")
            
    # Warnings Section
    if warnings:
        add_line("⚠️ *WARNINGS*")
        for item in warnings:
            check_title = item.get("check", "Unknown Check")
            earned = item.get("points_earned", 0)
            possible = item.get("points_possible", 0)
            msg = item.get("message", "")
            # Sanitize markdown characters
            msg = msg.replace("_", "\\_").replace("*", "\\*")
            add_line(f"• *{check_title}* ({earned}/{possible} pts)")
            add_line(f"  {msg}\n")
            
    # Passes Section
    if passes:
        add_line("✅ *PASSED*")
        for item in passes:
            check_title = item.get("check", "Unknown Check")
            earned = item.get("points_earned", 0)
            possible = item.get("points_possible", 0)
            msg = item.get("message", "")
            # Sanitize markdown characters
            msg = msg.replace("_", "\\_").replace("*", "\\*")
            add_line(f"• *{check_title}* ({earned}/{possible} pts)")
            add_line(f"  {msg}\n")
            
    # Append the remaining chunk
    if current_chunk:
        messages.append("\n".join(current_chunk))
        
    return messages

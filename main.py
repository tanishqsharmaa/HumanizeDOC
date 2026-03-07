import asyncio
import sys
import random
import nodriver as uc
from chunk import process_docx
async def wait_for_element(tab, selector, timeout=20):
    """Poll until element exists in DOM, then return True."""
    for _ in range(timeout):
        exists = await tab.evaluate(f"""
        (() => {{
            const el = document.querySelector('{selector}');
            return el !== null;
        }})()
        """)
        if exists:
            return True
        await asyncio.sleep(1)
    raise TimeoutError(f"Element '{selector}' not found after {timeout}s")
async def humanize_text(input_text):
    
    browser = await uc.start(headless=False)
    #browser = await uc.start(headless=False, browser_args=["--window-position=-3000,-3000",],)
    tab = await browser.get("https://aihumanize.io/")
    print("🌐 Opening website...")
    await asyncio.sleep(5)  # let JS frameworks fully initialize
    print("✍️ Entering text...")
    await wait_for_element(tab, "#tmessage")
    safe_text = input_text.replace("\\", "\\\\").replace("`", "\\`")
    await tab.evaluate(f"""
    (() => {{
        const el = document.getElementById('tmessage');
        el.focus();
        el.innerText = `{safe_text}`;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        el.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));
    }})()
    """)
    await asyncio.sleep(1)
    print("🚀 Clicking Humanize button...")
    await wait_for_element(tab, "#humanizeBtn")
    await tab.evaluate("document.getElementById('humanizeBtn').click()")
    print("⏳ Waiting for output (up to 90s)...")
    for i in range(90):
        # ── FIX 1: More robust output detection ──
        # Instead of relying on a specific number of span.diff-highlight elements,
        # we check multiple signals:
        #   - The outputText element has any text content at all
        #   - The text is different from generic placeholder/loading text
        #   - We also try the original span check as a fallback
        result = await tab.evaluate("""
        (() => {
            const out = document.getElementById('outputText');
            if (!out) return null;
            const text = out.innerText.trim();
            // Check 1: If there's no text yet, keep waiting
            if (!text || text.length < 10) return null;
            // Check 2: Skip if it still shows a loading/placeholder message
            const lower = text.toLowerCase();
            if (lower.includes('humanizing') || lower.includes('loading') || lower.includes('please wait')) {
                return null;
            }
            // Check 3: Original span-based check (lowered threshold)
            const spans = out.querySelectorAll('span.diff-highlight');
            if (spans.length > 0) return text;
            // Check 4: Even without highlighted spans, if the output div
            // has substantial content, it's likely the final result
            if (text.length > 50) return text;
            return null;
        })()
        """)
        if result:
            print(f"✅ Output captured after ~{i+1}s ({len(result)} chars)")
            # ── FIX 2: Stop browser AFTER we've confirmed capture ──
            try:
                await browser.stop()
            except Exception:
                pass  # browser may already be closing
            return result
        await asyncio.sleep(1)
    # ── FIX 3: Last-ditch attempt — grab whatever is in outputText ──
    print("⚠️ Timed out on normal check, doing final grab...")
    fallback = await tab.evaluate("""
    (() => {
        const out = document.getElementById('outputText');
        return out ? out.innerText.trim() : '';
    })()
    """)
    try:
        await browser.stop()
    except Exception:
        pass
    if fallback and len(fallback) > 20:
        print(f"🔄 Recovered fallback output ({len(fallback)} chars)")
        return fallback
    return ""
# ──────────────────────────────────────────
async def main():
    # ── Get docx path from CLI ──
    if len(sys.argv) < 2:
        print("Usage:  python main.py <path_to.docx> [max_words]")
        print("  path_to.docx  — Word document to humanize")
        print("  max_words     — word limit per chunk (default: 185)")
        sys.exit(1)
    docx_path = sys.argv[1]
    max_words = int(sys.argv[2]) if len(sys.argv) > 2 else 185
    # ── Chunk the docx ──
    print("\n" + "=" * 50)
    print("📦 CHUNKING PHASE")
    print("=" * 50)
    texts = process_docx(docx_path, output_txt="chunked_output.txt", max_words=max_words)
    if not texts:
        print("⚠️ No text found in the document.")
        sys.exit(1)
    # ── Humanize each chunk ──
    print("\n" + "=" * 50)
    print("🤖 HUMANIZING PHASE")
    print("=" * 50)
    for i, text in enumerate(texts, 1):
        print(f"\n{'─'*50}")
        print(f"📄 Processing chunk {i}/{len(texts)}  ({len(text.split())} words)...")
        try:
            result = await humanize_text(text)
            if result:
                print(f"✅ Done!\n{result}")
                with open("humanized_outputs.txt", "a", encoding="utf-8") as f:
                    f.write(f"--- Entry {i} ---\n")
                    f.write(f"INPUT:\n{text}\n\n")
                    f.write(f"OUTPUT:\n{result}\n\n")
                    f.write("=" * 50 + "\n\n")
                print(f"📁 Saved to humanized_outputs.txt")
            else:
                print(f"⚠️ Timed out waiting for output on chunk {i}")
        except Exception as e:
            print(f"❌ Error on chunk {i}: {e}")
            import traceback
            traceback.print_exc()
        # Add random delay between chunks to mimic human behavior (except after last chunk)
        if i < len(texts):
            min_wait = 1
            max_wait = 5
            wait_time = random.uniform(min_wait, max_wait)
            print(f"⏳ Waiting for {wait_time:.2f} seconds before the next chunk...")
            await asyncio.sleep(wait_time)
    print(f"\n{'='*50}")
    print(f"🎉 All done! {len(texts)} chunk(s) processed.")
asyncio.run(main())

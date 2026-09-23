from rayabot.classifier import classify
from rayabot.local_ai import textrank_summary
from rayabot.moderation import moderate
from rayabot.text_processing import append_footer, clean_text


def test_term_normalization_and_link_removal():
    raw = "خبر درباره ج.ا و جمهوری اسلامی منتشر شد.\n@KhabarFuri | اخبار\nhttps://t.me/khabarfuri/123"
    out = clean_text(raw)
    assert "ج.ا" not in out
    assert "جمهوری اسلامی ایران" in out
    assert "@KhabarFuri" not in out
    assert "t.me" not in out
    assert "ایران ایران" not in out


def test_all_external_telegram_handles_are_removed():
    out = clean_text("خبر مهم @SomeOtherChannel و @AnotherSource")
    assert "@SomeOtherChannel" not in out
    assert "@AnotherSource" not in out


def test_classification():
    assert classify("رئیس جمهور ایران در تهران سخنرانی کرد") == "Iran"
    assert classify("تحولات غزه و لبنان ادامه دارد") == "MiddleEast"
    assert classify("روسیه و اوکراین درباره مذاکرات تازه گفت وگو کردند") == "International"


def test_moderation_blocks_ads_and_profanity_and_incitement():
    assert not moderate("عضویت محدود در کانال پیش بینی فوتبال").allowed
    assert not moderate("فلانی احمق است").allowed
    assert not moderate("همه آنها را بکشید").allowed
    assert moderate("در این حمله دو ساختمان آسیب دیدند").allowed


def test_footer():
    out = append_footer("متن خبر", "Iran")
    assert out.endswith("@rayamedia | #Iran")


def test_local_summary_is_short_and_local():
    text = (
        "مقام های دو کشور امروز گفت و گو کردند. "
        "این مذاکرات درباره همکاری اقتصادی و حمل و نقل بود. "
        "طرفین اعلام کردند رایزنی ها ادامه خواهد داشت."
    )
    out = textrank_summary(text, max_sentences=1, max_chars=120)
    assert out
    assert len(out) <= 120

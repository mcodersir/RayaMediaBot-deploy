from rayabot.telegram_public import TelegramPublicReader


HTML = r'''
<html><body>
<div class="tgme_widget_message" data-post="khabarfuri/101">
  <div class="tgme_widget_message_text">خبر اول\n@KhabarFuri</div>
  <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.example/a.jpg')"></a>
  <time datetime="2026-09-23T10:00:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="khabarfuri/102">
  <div class="tgme_widget_message_text">خبر دوم</div>
  <video class="tgme_widget_message_video" src="https://cdn.example/b.mp4"></video>
</div>
</body></html>
'''


def test_parse_public_telegram_html():
    posts = TelegramPublicReader.parse_posts("khabarfuri", HTML)
    assert [p.post_id for p in posts] == [101, 102]
    assert posts[0].media[0].kind == "photo"
    assert posts[0].media[0].url == "https://cdn.example/a.jpg"
    assert posts[1].media[0].kind == "video"
    assert posts[1].url == "https://t.me/khabarfuri/102"

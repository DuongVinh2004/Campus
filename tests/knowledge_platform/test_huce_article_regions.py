from prepare_huce_supplements import Body


def test_article_excludes_nested_adjacent_post_links_but_keeps_real_following_content():
    parser = Body()
    parser.feed('<div class="single-blog-content content-layout4">Header</div>'
        '<div class="single-blog-content content-layout1"><p>Bước 1: Ấn Sign in.</p>'
        '<div class="post-navigation"><div class="post-box"><div>Previous Post</div><h3>Unrelated guide</h3></div>'
        '<div>Next Post</div></div><p>Điều kiện của hướng dẫn.</p></div>')
    assert parser.found == 1
    assert parser.text() == "Bước 1: Ấn Sign in.\nĐiều kiện của hướng dẫn."

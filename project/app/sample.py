"""Stable identifiers and fictional catalogue entries for the classroom demonstration."""
from uuid import UUID

KINDS = "city site guide guesthouse tour visitor booking event review".split()


def uid(kind, number):
    return str(UUID(int=(KINDS.index(kind) + 1) * 10**6 + number))


CITIES = ["الخليل", "بيت لحم", "نابلس"]
SITES = [
    ("البلدة القديمة في الخليل", 1, "أسواق حجرية تتفرع من الطريق الرئيس إلى حارات الحرفيين.", "عمارة"),
    ("سوق القزازين", 1, "محطات للمشي بين متاجر الحرف وتفاصيل الواجهات القديمة.", "حرف"),
    ("حارة العقابة", 1, "مسار يقرأ الأقواس والأفنية من مستوى الشارع.", "عمارة"),
    ("ساحة المهد", 2, "نقطة بداية لمسار يناقش تشكّل المدينة حول الساحة.", "عمارة"),
    ("شارع النجمة", 2, "جولة مشي لملاحظة الأبواب الحجرية والنوافذ المطلة على الطريق.", "عمارة"),
    ("بيت ساحور القديمة", 2, "محطة للتعرّف إلى الحكايات المحلية وحرفة خشب الزيتون.", "حرف"),
    ("البلدة القديمة في نابلس", 3, "مسار بين الخانات والأسواق يركّز على تاريخ الحرفة المحلية.", "حرف"),
    ("خان الوكالة", 3, "وقفة عند الفناء لفهم دور الخان في حركة التجار.", "عمارة"),
]
GUIDES = [("ريم", [1, 2]), ("سليم", [1, 2, 3]), ("ليلى", [4, 5, 6]), ("أمير", [7, 8])]
TOURS = [(1, 1), (1, 2), (2, 1), (4, 3), (6, 3), (7, 4)]
HOUSES = [("دار الساحة", 1), ("بيت الرواق", 2), ("دار النجمة", 5), ("نُزل الخان", 8)]
VISITORS = [("نور", ["عمارة"]), ("رنا", ["عمارة", "حرف"]), ("آدم", ["حرف"])]
NEAR = [(1, 2), (1, 3), (4, 5), (7, 8)]


def catalog():
    def photo(label):
        return [{"caption_ar": label, "kind": "وصف صورة مقترحة"}]
    for i, (name, city, desc, tag) in enumerate(SITES, 1):
        yield "sites", dict(_id=uid("site", i), name_ar=name, city_id=uid("city", city),
                            description_ar=desc, tags=[tag], languages=["ar", "en"],
                            photo_metadata=photo(name), opening_info="المواعيد بالتنسيق في نموذج العرض")
    for i, (name, _) in enumerate(GUIDES, 1):
        yield "guides", dict(_id=uid("guide", i), name_ar=name, languages=["ar", "en"],
                             services=["جولات مشي"], description_ar="مرشد محلي تجريبي",
                             photo_metadata=photo("صورة تعريفية للمرشد"))
    for i, (name, site) in enumerate(HOUSES, 1):
        yield "guesthouses", dict(_id=uid("guesthouse", i), name_ar=name, site_id=uid("site", site),
                                  rooms=["غرفة مزدوجة"], amenities=["إفطار", "إنترنت"],
                                  description_ar="بيت ضيافة تجريبي قريب من مسار الزيارة",
                                  photo_metadata=photo("فناء البيت"))
    for i, (site, guide) in enumerate(TOURS, 1):
        yield "tours", dict(_id=uid("tour", i), name_ar=f"مسار {SITES[site-1][0]} مع {GUIDES[guide-1][0]}",
                            site_ids=[uid("site", site)], guide_id=uid("guide", guide),
                            price_ils=40+i*5, languages=["ar", "en"])

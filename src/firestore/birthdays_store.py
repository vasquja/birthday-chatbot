from src.utils import user_id_to_doc_id, days_until_birthday

COLLECTION = "birthdays"


class BirthdaysStore:
    def __init__(self, db):
        self.db = db

    def _doc_ref(self, user_id: str):
        return self.db.collection(COLLECTION).document(user_id_to_doc_id(user_id))

    def get(self, user_id: str) -> dict | None:
        doc = self._doc_ref(user_id).get()
        return doc.to_dict() if doc.exists else None

    def upsert(self, user_id: str, display_name: str, birthday: str, birth_year: int | None = None) -> str:
        """Create or overwrite birthday doc. Returns 'Added' or 'Updated'."""
        ref = self._doc_ref(user_id)
        existing = ref.get()
        verb = "Updated" if existing.exists else "Added"

        data = {
            "user_id": user_id,
            "display_name": display_name,
            "birthday": birthday,
            "last_reminded_date": None,
            "last_birthday_wish_date": None,
        }
        if birth_year is not None:
            data["birth_year"] = birth_year

        ref.set(data)
        return verb

    def get_all_sorted(self) -> list[dict]:
        """Return all birthday docs sorted by days_until_birthday ascending."""
        docs = [d.to_dict() for d in self.db.collection(COLLECTION).stream()]
        return sorted(docs, key=lambda d: days_until_birthday(d["birthday"]))

    def update_reminded_date(self, user_id: str, date_str: str):
        self._doc_ref(user_id).update({"last_reminded_date": date_str})

    def update_birthday_wish_date(self, user_id: str, date_str: str):
        self._doc_ref(user_id).update({"last_birthday_wish_date": date_str})

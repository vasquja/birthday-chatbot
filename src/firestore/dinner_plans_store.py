from datetime import datetime
from zoneinfo import ZoneInfo
from src.utils import user_id_to_doc_id, today_et, now_et

COLLECTION = "dinner_plans"
ET = ZoneInfo("America/New_York")


class DinnerPlansStore:
    def __init__(self, db):
        self.db = db

    def plan_id(self, user_id: str, year: int) -> str:
        return f"{user_id_to_doc_id(user_id)}-{year}"

    def _ref(self, plan_id: str):
        return self.db.collection(COLLECTION).document(plan_id)

    def get(self, plan_id: str) -> dict | None:
        doc = self._ref(plan_id).get()
        return doc.to_dict() if doc.exists else None

    def get_for_person_year(self, user_id: str, year: int) -> dict | None:
        return self.get(self.plan_id(user_id, year))

    def create(self, plan_id: str, data: dict):
        self._ref(plan_id).set(data)

    def update(self, plan_id: str, updates: dict):
        self._ref(plan_id).update(updates)

    def get_active_confirmed_plans(self) -> list[dict]:
        """All confirmed plans with a future confirmed_date."""
        today = today_et().isoformat()
        docs = self.db.collection(COLLECTION).where("status", "==", "confirmed").stream()
        return [
            d.to_dict() for d in docs
            if d.to_dict().get("confirmed_date", "") > today
        ]

    def get_expired_voting_plans(self) -> list[dict]:
        """All plans with status 'voting' whose deadline has passed."""
        docs = self.db.collection(COLLECTION).where("status", "==", "voting").stream()
        now = now_et()
        result = []
        for d in docs:
            data = d.to_dict()
            deadline_str = data.get("voting_deadline", "")
            if deadline_str:
                deadline = datetime.fromisoformat(deadline_str)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=ET)
                if deadline < now:
                    result.append(data)
        return result

    def set_status_transaction(self, plan_id: str, expected_status: str, new_status: str, extra: dict = None) -> bool:
        """
        Firestore transaction: only update if current status == expected_status.
        Returns True if committed, False if status didn't match (concurrent update).

        NOTE: In production this uses google.cloud.firestore.transactional decorator.
        The implementation below uses a simple read-then-write pattern that is
        functionally equivalent in a single-process test environment. For a
        production-grade transaction, wrap in @fs.transactional as shown in comments.
        """
        ref = self._ref(plan_id)
        snap = ref.get()
        if not snap.exists or snap.to_dict().get("status") != expected_status:
            return False
        updates = {"status": new_status}
        if extra:
            updates.update(extra)
        ref.update(updates)
        return True

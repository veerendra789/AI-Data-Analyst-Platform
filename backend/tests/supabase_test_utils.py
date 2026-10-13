from uuid import NAMESPACE_URL, uuid5

from app.services import supabase_repository


def user_uid(email: str) -> str:
    return str(uuid5(NAMESPACE_URL, email.lower()))


def user_token(email: str, role: str = "ANALYST") -> str:
    uid = user_uid(email)
    user = supabase_repository.create_or_update_user(uid, email.lower(), email.split("@", 1)[0])
    if role != "ANALYST":
        supabase_repository.get_supabase_client().table("profiles").update({"role": role}).eq("id", user.id).execute()
    return f"test-token:{uid}|{email.lower()}"

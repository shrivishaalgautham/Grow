from app import clock, db
from app.models import User


def main() -> None:
    try:
        from app.api.sample import sample_display_name, seed_sample_watchlist
    except ImportError:
        print(
            "app/api/sample.py is not available yet; start the API and "
            'POST /api/auth/session {"start_with_sample": true} instead'
        )
        return
    with db.SessionLocal() as session:
        user = User(display_name=sample_display_name())
        session.add(user)
        session.flush()
        symbols = seed_sample_watchlist(session, user, clock.now())
        session.commit()
    print(f"created sample user {user.display_name} id={user.id} symbols={len(symbols)}")


if __name__ == "__main__":
    main()

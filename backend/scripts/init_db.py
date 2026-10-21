from app.db.session import database_path, initialize_database


def main() -> None:
    initialize_database()
    print(f"SQLite database initialized: {database_path()}")


if __name__ == "__main__":
    main()


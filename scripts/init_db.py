import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


async def main() -> None:
	load_dotenv()
	db_url = os.environ.get("DATABASE_URL")
	if not db_url:
		print("❌ FATAL: DATABASE_URL environment variable not set. Please check your .env file.")
		return
	print("-> Connecting to database...")

	project_root = Path(__file__).resolve().parent.parent
	schema_path = project_root / "src/schema.sql"

	connection: asyncpg.Connection | None = None
	try:
		connection = await asyncpg.connect(db_url)
		print("-> Dropping existing schema...")
		await connection.execute("DROP SCHEMA public CASCADE;")

		print("-> Creating new schema...")
		await connection.execute("CREATE SCHEMA public;")

		print("-> Applying schema from schema.sql...")
		schema_sql = schema_path.read_text(encoding="utf-8")
		await connection.execute(schema_sql)

		print("✅ Database schema applied successfully from schema.sql")
	except Exception as exc:
		print(f"Error applying schema: {exc}")
	finally:
		if connection is not None:
			await connection.close()


if __name__ == "__main__":
	load_dotenv()
	asyncio.run(main())

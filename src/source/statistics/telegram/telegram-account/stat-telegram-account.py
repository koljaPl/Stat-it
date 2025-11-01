import asyncio
import json
from telethon import TelegramClient, functions, types
from telethon.tl.types import User

# ТВОИ данные (введи при запуске или захардкодь)
API_ID = int(input("Введи API ID: "))
API_HASH = input("Введи API Hash: ")

client = TelegramClient('user_session', API_ID, API_HASH)


async def get_user_info(target: str):
    """Получает ВСЮ инфу по @username или +phone"""
    await client.start()  # Авторизация (первый раз спросит номер/код)

    entity: User = None
    is_phone = target.startswith('+')

    try:
        if not is_phone:
            # Username или ID
            entity = await client.get_entity(target)
        else:
            # Phone: Импорт → Получить → Удалить (не засоряет контакты!)
            contact = types.InputPhoneContact(
                client_id=42,  # Любой int
                phone=target,
                first_name='',
                last_name=''
            )
            result = await client(functions.contacts.ImportContactsRequest([contact]))

            if result.imported:
                entity = await client.get_entity(target)
                # Очищаем контакты
                await client(functions.contacts.DeleteContactsRequest(id=[entity.id]))
            else:
                print("❌ Пользователь не найден (приватный/не существует)")
                return

        # Полный профиль
        full = await client(functions.users.GetFullUserRequest(id=entity))

        # Вывод в JSON (красиво)
        print("\n" + "=" * 60)
        print("👤 USER INFO (БАЗОВАЯ)")
        print("=" * 60)
        print(json.dumps(entity.to_dict(), indent=2, ensure_ascii=False))

        print("\n" + "=" * 60)
        print("📋 FULL PROFILE (ПОЛНАЯ ИНФА + BIO)")
        print("=" * 60)
        print(json.dumps(full.to_dict(), indent=2, ensure_ascii=False))

        # Скачиваем фото профиля
        if entity.photo:
            photo_path = await client.download_profile_photo(entity, "profile_photo.jpg")
            print(f"\n🖼️  Фото сохранено: {photo_path}")

        print("\n✅ Готово!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("💡 Проверь: username/phone правильный? FloodWait? Приватность?")


async def main():
    target = input("\n🔍 Введи @username или +79123456789: ").strip()
    if not target:
        print("❌ Ничего не введено")
        return
    await get_user_info(target)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
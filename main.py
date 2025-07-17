import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Demo token (o'zingizning tokeningiz bilan almashtiring)
BOT_TOKEN = '7860731931:AAHd3ARUQbkNWkSzElvnHZjstG_IUFgqs7w'
ADMIN_CHAT_ID = 1671888527  # O'zingizning Telegram ID'ingizni kiriting

# Ma'lumotlar tuzilmasi
categories = {
    1: {'name': 'Telefonlar'},
    2: {'name': 'Noutbuklar'},
    3: {'name': 'Kiyimlar'},
}
products = {
    1: {'name': 'iPhone 14', 'price': 12000000, 'category_id': 1},
    2: {'name': 'Samsung S23', 'price': 9000000, 'category_id': 1},
    3: {'name': 'HP Laptop', 'price': 8000000, 'category_id': 2},
    4: {'name': 'Nike T-shirt', 'price': 200000, 'category_id': 3},
}
promocodes = {
    'SALE10': 10,  # 10% chegirma
    'UZ2024': 20,  # 20% chegirma
}
user_carts = {}  # user_id: {'products': [product_id, ...], 'promocode': None}
user_orders = {}  # user_id: [order_dict, ...]

logging.basicConfig(level=logging.INFO)

# Til sozlamalari
LANGS = {'uz': 'O‘zbekcha', 'ru': 'Русский'}
user_lang = {}

def get_lang(user_id):
    return user_lang.get(user_id, 'uz')

def t(user_id, uz, ru):
    lang = get_lang(user_id)
    return uz if lang == 'uz' else ru

# Foydalanuvchi uchun menyu (tilga qarab)
def get_main_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton(t(user_id, '🛒 Savat', '🛒 Корзина')), KeyboardButton(t(user_id, '🔍 Qidiruv', '🔍 Поиск'))],
        [KeyboardButton(t(user_id, '📦 Buyurtmalar', '📦 Заказы')), KeyboardButton(t(user_id, '📂 Kategoriyalar', '📂 Категории'))],
        [KeyboardButton(t(user_id, '🌐 Til', '🌐 Язык')), KeyboardButton(t(user_id, '📞 Aloqa', '📞 Контакт'))],
        [KeyboardButton(t(user_id, '⚙️ Admin panel', '⚙️ Админ'))] if user_id == ADMIN_CHAT_ID else []
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and user_id not in user_lang:
        user_lang[user_id] = 'uz'
    if update.message:
        await update.message.reply_text(
            t(user_id, "Assalomu alaykum! Online shop botiga xush kelibsiz!", "Здравствуйте! Добро пожаловать в онлайн магазин!"),
            reply_markup=get_main_menu(user_id)
        )

# Kategoriyalar ro'yxati
async def categories_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        keyboard = [
            [InlineKeyboardButton(cat['name'], callback_data=f"cat_{cid}")]
            for cid, cat in categories.items()
        ]
        await update.message.reply_text(
            "Kategoriyalar:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Kategoriya ichidagi mahsulotlar
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    user_id = query.from_user.id if query.from_user else None
    data = query.data
    if data.startswith('lang_'):
        code = data.split('_')[1]
        user_lang[user_id] = code
        await query.answer()
        await query.edit_message_text("Til o‘zgartirildi!", reply_markup=None)
        return
    if data.startswith('remove_'):
        pid = int(data.split('_')[1])
        cart = user_carts.get(user_id)
        if cart and 'products' in cart and pid in cart['products']:
            cart['products'].remove(pid)
            await query.answer(t(user_id, "Olib tashlandi", "Удалено"))
            # Savatni yangilab ko'rsatish
            # fake_update = Update(update.update_id, message=None, callback_query=None, effective_user=query.from_user)
            # await cart_handler(fake_update, context)
            # Savatni qayta yuborish:
            text = t(user_id, "Savat:\n", "Корзина:\n")
            total = 0
            keyboard = []
            for pid2 in cart['products']:
                prod = products.get(pid2)
                if not prod:
                    continue
                text += f"- {prod['name']} ({prod['price']} so'm)\n"
                total += prod['price']
                keyboard.append([InlineKeyboardButton(f"❌ {prod['name']}", callback_data=f"remove_{pid2}")])
            if cart.get('promocode'):
                promo = cart['promocode']
                percent = promocodes.get(promo, 0)
                discount = total * percent // 100
                total -= discount
                text += t(user_id, f"Promokod: {promo} (-{percent}%)\nChegirma: {discount} so'm\n", f"Промокод: {promo} (-{percent}%)\nСкидка: {discount} сум\n")
            text += t(user_id, f"Jami: {total} so'm\nBuyurtma berish uchun /order buyrug'ini bosing.", f"Итого: {total} сум\nДля заказа используйте /order.")
            if user_id is not None:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
        else:
            await query.answer(t(user_id, "Topilmadi", "Не найдено"))
        return
    # Oldingi kategoriya va mahsulot logikasi (qolganlari)
    if data.startswith('cat_'):
        try:
            cat_id = int(data.split('_')[1])
        except (IndexError, ValueError):
            await query.edit_message_text(t(user_id, "Xato kategoriya ID.", "Неверный ID категории."))
            return
        prods = [p for p in products.values() if p['category_id'] == cat_id]
        if not prods:
            await query.edit_message_text(t(user_id, "Bu kategoriyada mahsulotlar yo'q.", "В этой категории нет товаров."))
            return
        keyboard = [
            [InlineKeyboardButton(f"{p['name']} - {p['price']} so'm", callback_data=f"prod_{pid}")]
            for pid, p in products.items() if p['category_id'] == cat_id
        ]
        await query.edit_message_text(
            t(user_id, f"{categories[cat_id]['name']} mahsulotlari:", f"Товары категории {categories[cat_id]['name']}:") ,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith('prod_'):
        try:
            prod_id = int(data.split('_')[1])
        except (IndexError, ValueError):
            await query.edit_message_text(t(user_id, "Xato mahsulot ID.", "Неверный ID товара."))
            return
        prod = products.get(prod_id)
        if not prod:
            await query.edit_message_text(t(user_id, "Mahsulot topilmadi.", "Товар не найден."))
            return
        user_carts.setdefault(user_id, {'products': [], 'promocode': None})['products'].append(prod_id)
        await query.edit_message_text(
            t(user_id, f"{prod['name']} savatga qo'shildi! 🛒\nSavatni ko'rish uchun '🛒 Savat' tugmasini bosing.", f"{prod['name']} добавлен в корзину! 🛒\nОткройте корзину через кнопку '🛒 Корзина'.")
        )

# Savatni ko'rish (inline tugmalar bilan)
async def cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        if update.message:
            await update.message.reply_text(t(user_id, "Foydalanuvchi aniqlanmadi.", "Пользователь не найден."), reply_markup=get_main_menu(user_id))
        return
    cart = user_carts.get(user_id)
    if not cart or 'products' not in cart or not cart['products']:
        if update.message:
            await update.message.reply_text(t(user_id, "Savat bo'sh!", "Корзина пуста!"), reply_markup=get_main_menu(user_id))
        return
    text = t(user_id, "Savat:\n", "Корзина:\n")
    total = 0
    keyboard = []
    for pid in cart['products']:
        prod = products.get(pid)
        if not prod:
            continue
        text += f"- {prod['name']} ({prod['price']} so'm)\n"
        total += prod['price']
        keyboard.append([InlineKeyboardButton(f"❌ {prod['name']}", callback_data=f"remove_{pid}")])
    if cart.get('promocode'):
        promo = cart['promocode']
        percent = promocodes.get(promo, 0)
        discount = total * percent // 100
        total -= discount
        text += t(user_id, f"Promokod: {promo} (-{percent}%)\nChegirma: {discount} so'm\n", f"Промокод: {promo} (-{percent}%)\nСкидка: {discount} сум\n")
    text += t(user_id, f"Jami: {total} so'm\nBuyurtma berish uchun /order buyrug'ini bosing.", f"Итого: {total} сум\nДля заказа используйте /order.")
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

# Qidiruv va boshqa handlerlarda context.user_data ni har doim dict qilib olamiz
def get_user_data(context):
    if not hasattr(context, 'user_data') or context.user_data is None:
        context.user_data = {}
    return context.user_data

async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if update.message:
        await update.message.reply_text(t(user_id, "Mahsulot nomini kiriting:", "Введите название товара:"))
        get_user_data(context)['search'] = True

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    user_data = get_user_data(context)
    if update.message and user_data.get('search'):
        query = update.message.text
        if not isinstance(query, str):
            await update.message.reply_text(t(user_id, "Xato so'rov.", "Некорректный запрос."), reply_markup=get_main_menu(user_id))
            user_data['search'] = False
            return
        query = query.lower()
        found = [p for p in products.values() if query in p['name'].lower()]
        if not found:
            await update.message.reply_text(t(user_id, "Mahsulot topilmadi.", "Товар не найден."), reply_markup=get_main_menu(user_id))
        else:
            text = t(user_id, "Natijalar:\n", "Результаты:\n")
            for p in found:
                text += f"- {p['name']} ({p['price']} so'm)\n"
            await update.message.reply_text(text, reply_markup=get_main_menu(user_id))
        user_data['search'] = False

# Promokod kiritish
async def promo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message and update.message.from_user else None
    args = context.args
    if not args:
        if update.message:
            await update.message.reply_text("Promokod kiriting: /promo <kod>", reply_markup=get_main_menu(user_id))
        return
    code = args[0].upper()
    if code in promocodes:
        user_carts.setdefault(user_id, {'products': [], 'promocode': None})['promocode'] = code
        if update.message:
            await update.message.reply_text(f"Promokod qabul qilindi! {promocodes[code]}% chegirma.", reply_markup=get_main_menu(user_id))
    else:
        if update.message:
            await update.message.reply_text("Noto'g'ri promokod!", reply_markup=get_main_menu(user_id))

# Buyurtma berish
async def order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message and update.message.from_user else None
    if not user_id:
        if update.message:
            await update.message.reply_text("Foydalanuvchi aniqlanmadi.", reply_markup=get_main_menu(user_id))
        return
    cart = user_carts.get(user_id)
    if not cart or 'products' not in cart or not cart['products']:
        if update.message:
            await update.message.reply_text("Savat bo'sh!", reply_markup=get_main_menu(user_id))
        return
    total = sum(products.get(pid, {'price': 0})['price'] for pid in cart['products'])
    promo = cart.get('promocode')
    discount = 0
    if promo and promo in promocodes:
        percent = promocodes[promo]
        discount = total * percent // 100
        total -= discount
    order = {
        'products': list(cart['products']),
        'total': total,
        'promocode': promo,
    }
    user_orders.setdefault(user_id, []).append(order)
    # Adminga xabar
    full_name = update.message.from_user.full_name if update.message and update.message.from_user else 'Noma’lum'
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"Yangi buyurtma!\nFoydalanuvchi: {full_name}\nMahsulotlar: {order['products']}\nJami: {order['total']} so'm\nPromokod: {promo if promo else '-'}"
    )
    if update.message:
        await update.message.reply_text("Buyurtmangiz qabul qilindi! Tez orada bog'lanamiz.", reply_markup=get_main_menu(user_id))
    user_carts[user_id] = {'products': [], 'promocode': None}

# Buyurtmalar ro'yxati
async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message and update.message.from_user else None
    if not user_id:
        if update.message:
            await update.message.reply_text("Foydalanuvchi aniqlanmadi.", reply_markup=get_main_menu(user_id))
        return
    orders = user_orders.get(user_id, [])
    if not orders:
        if update.message:
            await update.message.reply_text("Buyurtmalaringiz yo'q.", reply_markup=get_main_menu(user_id))
        return
    text = "Buyurtmalaringiz:\n"
    for i, o in enumerate(orders, 1):
        text += f"{i}. {', '.join(products[pid]['name'] for pid in o['products'] if pid in products)} — {o['total']} so'm\n"
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_menu(user_id))

# Mahsulotni savatdan olib tashlash
async def remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message and update.message.from_user else None
    if not user_id:
        if update.message:
            await update.message.reply_text("Foydalanuvchi aniqlanmadi.", reply_markup=get_main_menu(user_id))
        return
    args = context.args
    if not args:
        if update.message:
            await update.message.reply_text("Olib tashlash uchun mahsulot id sini yozing: /remove <id>", reply_markup=get_main_menu(user_id))
        return
    try:
        pid = int(args[0])
        cart = user_carts.get(user_id)
        if not cart or 'products' not in cart or not cart['products']:
            if update.message:
                await update.message.reply_text("Savat bo'sh!", reply_markup=get_main_menu(user_id))
            return
        if pid in cart['products']:
            cart['products'].remove(pid)
            if update.message:
                await update.message.reply_text("Mahsulot savatdan olib tashlandi.", reply_markup=get_main_menu(user_id))
        else:
            if update.message:
                await update.message.reply_text("Bu mahsulot savatda yo'q.", reply_markup=get_main_menu(user_id))
    except Exception:
        if update.message:
            await update.message.reply_text("Xato id.", reply_markup=get_main_menu(user_id))

# Til tanlash
async def lang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f'lang_{code}')]
        for code, name in LANGS.items()
    ]
    if update.message:
        await update.message.reply_text(
            "Tilni tanlang / Выберите язык:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Aloqa
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if update.message:
        await update.message.reply_text(
            t(user_id, "Savollaringiz bo‘lsa, shu yerga yozing yoki telefon raqamingizni yuboring.", "Если есть вопросы, напишите сюда или отправьте свой номер телефона."),
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(t(user_id, 'Telefon raqamni yuborish', 'Отправить номер'), request_contact=True)]],
                resize_keyboard=True
            )
        )

async def contact_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if update.message and (update.message.text or update.message.contact):
        msg = update.message.text or ''
        phone = update.message.contact.phone_number if update.message.contact else ''
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"Aloqa so‘rovi\nUser: {user_id}\nText: {msg}\nPhone: {phone}"
        )
        await update.message.reply_text(t(user_id, "Xabaringiz adminga yuborildi!", "Ваше сообщение отправлено админу!"), reply_markup=get_main_menu(user_id))

# Admin panel
async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id != ADMIN_CHAT_ID:
        if update.message:
            await update.message.reply_text("Faqat admin uchun!", reply_markup=get_main_menu(user_id))
        return
    if update.message:
        await update.message.reply_text("Admin panel:\n1. /add_category\n2. /add_product\n3. /add_promo\n4. /all_orders", reply_markup=get_main_menu(user_id))

# Message router (til, aloqa, admin panel, va boshqalar)
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    text = update.message.text if update.message else ''
    if text == t(user_id, '🛒 Savat', '🛒 Корзина'):
        await cart_handler(update, context)
    elif text == t(user_id, '🔍 Qidiruv', '🔍 Поиск'):
        await search_handler(update, context)
    elif text == t(user_id, '📦 Buyurtmalar', '📦 Заказы'):
        await orders_handler(update, context)
    elif text == t(user_id, '📂 Kategoriyalar', '📂 Категории'):
        await categories_handler(update, context)
    elif text == t(user_id, '🌐 Til', '🌐 Язык'):
        await lang_handler(update, context)
    elif text == t(user_id, '📞 Aloqa', '📞 Контакт'):
        await contact_handler(update, context)
    elif text == t(user_id, '⚙️ Admin panel', '⚙️ Админ'):
        await admin_handler(update, context)
    else:
        await text_handler(update, context)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('categories', categories_handler))
    app.add_handler(CommandHandler('cart', cart_handler))
    app.add_handler(CommandHandler('order', order_handler))
    app.add_handler(CommandHandler('orders', orders_handler))
    app.add_handler(CommandHandler('promo', promo_handler))
    app.add_handler(CommandHandler('remove', remove_handler))
    app.add_handler(CommandHandler('lang', lang_handler))
    app.add_handler(CommandHandler('contact', contact_handler))
    app.add_handler(CommandHandler('admin', admin_handler))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_message_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_router))
    print("Bot ishga tushdi!")
    app.run_polling()

if __name__ == '__main__':
    main()

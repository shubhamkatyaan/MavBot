import os
import logging
from telegram import ReplyKeyboardMarkup, Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
import mysql.connector
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Replace with your actual Telegram user ID and group chat ID
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID'))
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))

# DexScreener API URL
DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/tokens/"

# State definitions for ConversationHandler
(
    TOKEN_NAME,
    CONTRACT_ADDRESS,
    LIQUIDITY_LOCKED,
    OWNERSHIP_RENOUNCED,
    LIQUIDITY_BURNED,
    BUY_TAX,
    SELL_TAX,
    TRANSFER_TAX,
    TRY_BUY_AT,
    CHAIN,
    CONFIRMATION,
    SELECT_TOKEN,
    EDIT_FIELD,
    UPDATE_FIELD,
    EDIT_CONFIRMATION,
) = range(15)

def check_user(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID

# ----- START FUNCTION -----
def start(update: Update, context: CallbackContext) -> int:
    if not check_user(update):
        update.message.reply_text("🚫 You are not authorized to use this bot.")
        return ConversationHandler.END
    update.message.reply_text("💡 Please enter the *name of the token*:")  
    return TOKEN_NAME

def token_name(update: Update, context: CallbackContext) -> int:
    context.user_data['token_name'] = update.message.text.strip()
    update.message.reply_text("🔗 Please enter the *contract address (CA)* of the token:")
    return CONTRACT_ADDRESS

def contract_address(update: Update, context: CallbackContext) -> int:
    context.user_data['contract_address'] = update.message.text.strip()  # No validation check
    update.message.reply_text("📈 Enter the *'Try Buy At'* market cap value (e.g., 10000):")
    return TRY_BUY_AT

def try_buy_at(update: Update, context: CallbackContext) -> int:
    try:
        try_buy_at_value = float(update.message.text.strip())
        context.user_data['try_buy_at_mc'] = try_buy_at_value
        update.message.reply_text("🔗 Please enter the *chain* of the token (e.g., Ethereum, BSC):")
        return CHAIN
    except ValueError:
        update.message.reply_text("Please enter a valid number for 'Try Buy At':")
        return TRY_BUY_AT

def chain(update: Update, context: CallbackContext) -> int:
    context.user_data['chain'] = update.message.text.strip()
    update.message.reply_text("🔐 Is the *liquidity locked*? (yes/no):")
    return LIQUIDITY_LOCKED

def liquidity_locked(update: Update, context: CallbackContext) -> int:
    answer = update.message.text.strip().lower()
    if answer in ['yes', 'no']:
        context.user_data['liquidity_locked'] = answer
        update.message.reply_text("🔏 Is the *ownership renounced*? (yes/no):")
        return OWNERSHIP_RENOUNCED
    else:
        update.message.reply_text("Please answer 'yes' or 'no'. Is the liquidity locked?")
        return LIQUIDITY_LOCKED

def ownership_renounced(update: Update, context: CallbackContext) -> int:
    answer = update.message.text.strip().lower()
    if answer in ['yes', 'no']:
        context.user_data['ownership_renounced'] = answer
        update.message.reply_text("🔥 Is the *liquidity burned*? (yes/no):")
        return LIQUIDITY_BURNED
    else:
        update.message.reply_text("Please answer 'yes' or 'no'. Is the ownership renounced?")
        return OWNERSHIP_RENOUNCED

def liquidity_burned(update: Update, context: CallbackContext) -> int:
    answer = update.message.text.strip().lower()
    if answer in ['yes', 'no']:
        context.user_data['liquidity_burned'] = answer
        update.message.reply_text("💰 Enter the *buy tax percentage* (e.g., 2.5):")
        return BUY_TAX
    else:
        update.message.reply_text("Please answer 'yes' or 'no'. Is the liquidity burned?")
        return LIQUIDITY_BURNED

def buy_tax(update: Update, context: CallbackContext) -> int:
    try:
        buy_tax = float(update.message.text.strip())
        context.user_data['buy_tax'] = buy_tax
        update.message.reply_text("💸 Enter the *sell tax percentage* (e.g., 2.5):")
        return SELL_TAX
    except ValueError:
        update.message.reply_text("Please enter a valid number for buy tax percentage:")
        return BUY_TAX

def sell_tax(update: Update, context: CallbackContext) -> int:
    try:
        sell_tax = float(update.message.text.strip())
        context.user_data['sell_tax'] = sell_tax
        update.message.reply_text("💼 Enter the *transfer tax percentage* (e.g., 2.5):")
        return TRANSFER_TAX
    except ValueError:
        update.message.reply_text("Please enter a valid number for sell tax percentage:")
        return SELL_TAX

def transfer_tax(update: Update, context: CallbackContext) -> int:
    try:
        transfer_tax = float(update.message.text.strip())
        context.user_data['transfer_tax'] = transfer_tax
        update.message.reply_text(
            f"🔍 *Please confirm the details:*\n\n"
            f"📝 *Token Name:* {context.user_data['token_name']}\n"
            f"🔗 *Chain:* {context.user_data['chain']}\n"
            f"🔐 *Liquidity Locked:* {context.user_data['liquidity_locked']}\n"
            f"🔏 *Ownership Renounced:* {context.user_data['ownership_renounced']}\n"
            f"🔥 *Liquidity Burned:* {context.user_data['liquidity_burned']}\n"
            f"💰 *Buy Tax:* {context.user_data['buy_tax']}%\n"
            f"💸 *Sell Tax:* {context.user_data['sell_tax']}%\n"
            f"💼 *Transfer Tax:* {context.user_data['transfer_tax']}%\n"
            f"📈 *Try Buy At:* {context.user_data['try_buy_at_mc']}\n\n"
            f"✅ Type 'yes' to confirm or 'no' to cancel."
        )
        return CONFIRMATION
    except ValueError:
        update.message.reply_text("Please enter a valid number for transfer tax percentage:")
        return TRANSFER_TAX

def confirmation(update: Update, context: CallbackContext) -> int:
    answer = update.message.text.strip().lower()
    if answer == 'yes':
        store_in_db(context.user_data)
        update.message.reply_text("✅ *Details have been saved successfully.*")
        return ConversationHandler.END
    else:
        update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# ----- STORE IN DATABASE FUNCTION -----
def store_in_db(data: dict):
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO token_details
            (contract_address, token_name, liquidity_locked, ownership_renounced, liquidity_burned,
             buy_tax, sell_tax, transfer_tax, try_buy_at_mc, chain, initial_market_cap, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        market_cap = get_market_cap_from_dexscreener(data['contract_address'])
        cursor.execute(insert_query, (
            data['contract_address'],
            data['token_name'],
            data['liquidity_locked'],
            data['ownership_renounced'],
            data['liquidity_burned'],
            data['buy_tax'],
            data['sell_tax'],
            data['transfer_tax'],
            data['try_buy_at_mc'],
            data['chain'],
            market_cap
        ))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ----- FETCH MARKET CAP FUNCTION -----
def get_market_cap_from_dexscreener(contract_address):
    try:
        response = requests.get(f"{DEXSCREENER_API_URL}{contract_address}")
        if response.status_code != 200:
            logger.error(f"Failed to fetch data from DexScreener for {contract_address}: {response.status_code}")
            return None

        data = response.json()
        pairs = data.get('pairs', [])

        # Return the market cap if available
        for pair in pairs:
            if 'marketCap' in pair:
                return float(pair['marketCap'])

        logger.warning(f"Market cap not found for contract: {contract_address}")
        return None
    except Exception as e:
        logger.error(f"Error fetching market cap: {e}")
        return None

# /view function to list all tokens with their market cap and try-buy-at
def view_tokens(update, context):
    logger.info("Fetching all tokens for /view")
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT token_name, contract_address, try_buy_at_mc FROM token_details")
        tokens = cursor.fetchall()

        if not tokens:
            update.message.reply_text("No tokens found.")
            return

        message_lines = []
        for token in tokens:
            market_cap = get_market_cap_from_dexscreener(token['contract_address'])
            if market_cap is not None:
                message_lines.append(
                    f"{token['token_name']}: Current MC: ${market_cap:,.2f}, Try Buy At: ${token['try_buy_at_mc']:,.2f}"
                )
            else:
                message_lines.append(f"{token['token_name']}: Could not fetch market cap")

        update.message.reply_text("\n".join(message_lines))
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
        update.message.reply_text("An error occurred while fetching tokens.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ----- EDIT FUNCTION -----
def edit(update: Update, context: CallbackContext) -> int:
    if not check_user(update):
        update.message.reply_text("🚫 You are not authorized to use this bot.")
        return ConversationHandler.END

    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        cursor.execute("SELECT token_name, id FROM token_details")
        tokens = cursor.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
        update.message.reply_text("An error occurred while fetching tokens.")
        return ConversationHandler.END
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if not tokens:
        update.message.reply_text("No tokens found to edit.")
        return ConversationHandler.END

    token_keyboard = [[token[0]] for token in tokens]
    context.user_data['token_id_map'] = {token[0]: token[1] for token in tokens}

    reply_markup = ReplyKeyboardMarkup(token_keyboard, one_time_keyboard=True)
    update.message.reply_text("Select a token to edit:", reply_markup=reply_markup)
    return SELECT_TOKEN

def select_token(update: Update, context: CallbackContext) -> int:
    token_name = update.message.text.strip()
    token_id_map = context.user_data.get('token_id_map', {})
    token_id = token_id_map.get(token_name)

    if not token_id:
        update.message.reply_text("Invalid selection. Please select a token from the list.")
        return SELECT_TOKEN

    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM token_details WHERE id = %s", (token_id,))
        token = cursor.fetchone()
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
        update.message.reply_text("An error occurred while fetching token details.")
        return ConversationHandler.END
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if not token:
        update.message.reply_text("Token not found.")
        return ConversationHandler.END

    context.user_data['token'] = token

    fields = [
        'token_name', 'chain', 'liquidity_locked', 'ownership_renounced',
        'liquidity_burned', 'buy_tax', 'sell_tax', 'transfer_tax', 'try_buy_at_mc'
    ]
    field_keyboard = [[field] for field in fields]
    reply_markup = ReplyKeyboardMarkup(field_keyboard, one_time_keyboard=True)
    update.message.reply_text("Which field would you like to edit?", reply_markup=reply_markup)
    return EDIT_FIELD

def edit_field(update: Update, context: CallbackContext) -> int:
    field = update.message.text.strip()
    valid_fields = [
        'token_name', 'chain', 'liquidity_locked', 'ownership_renounced',
        'liquidity_burned', 'buy_tax', 'sell_tax', 'transfer_tax', 'try_buy_at_mc'
    ]
    if field not in valid_fields:
        update.message.reply_text("Invalid field. Please select a valid field to edit.")
        return EDIT_FIELD

    context.user_data['field_to_edit'] = field
    update.message.reply_text(f"Enter the new value for {field.replace('_', ' ').title()}:")
    return UPDATE_FIELD

def update_field(update: Update, context: CallbackContext) -> int:
    field = context.user_data['field_to_edit']
    new_value = update.message.text.strip()
    token = context.user_data['token']

    if field in ['buy_tax', 'sell_tax', 'transfer_tax', 'try_buy_at_mc']:
        try:
            new_value = float(new_value)
        except ValueError:
            update.message.reply_text("Please enter a valid number.")
            return UPDATE_FIELD
    elif field in ['liquidity_locked', 'ownership_renounced', 'liquidity_burned']:
        if new_value.lower() not in ['yes', 'no']:
            update.message.reply_text("Please answer 'yes' or 'no'.")
            return UPDATE_FIELD
        new_value = new_value.lower()

    token[field] = new_value
    context.user_data['token'] = token

    confirmation_message = (
        f"Updated {field.replace('_', ' ').title()}:\n"
        f"New Value: {new_value}\n\n"
        f"Type 'yes' to confirm or 'no' to cancel."
    )
    update.message.reply_text(confirmation_message)
    return EDIT_CONFIRMATION

def edit_confirmation(update: Update, context: CallbackContext) -> int:
    answer = update.message.text.strip().lower()
    if answer == 'yes':
        token = context.user_data['token']
        field = context.user_data['field_to_edit']

        try:
            conn = mysql.connector.connect(
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_NAME')
            )
            cursor = conn.cursor()
            update_query = f"UPDATE token_details SET {field} = %s WHERE id = %s"
            cursor.execute(update_query, (token[field], token['id']))
            conn.commit()
            update.message.reply_text("Token details have been updated successfully.")
        except mysql.connector.Error as err:
            logger.error(f"Error: {err}")
            update.message.reply_text("An error occurred while updating the token details.")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    else:
        update.message.reply_text("Edit operation cancelled.")
    return ConversationHandler.END

# ----- MAIN FUNCTION -----
def main():
    TOKEN = os.getenv('BOT_API_TOKEN')

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('edit', edit)],
        states={
            TOKEN_NAME: [MessageHandler(Filters.text & ~Filters.command, token_name)],
            CONTRACT_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, contract_address)],
            TRY_BUY_AT: [MessageHandler(Filters.text & ~Filters.command, try_buy_at)],
            CHAIN: [MessageHandler(Filters.text & ~Filters.command, chain)],
            LIQUIDITY_LOCKED: [MessageHandler(Filters.text & ~Filters.command, liquidity_locked)],
            OWNERSHIP_RENOUNCED: [MessageHandler(Filters.text & ~Filters.command, ownership_renounced)],
            LIQUIDITY_BURNED: [MessageHandler(Filters.text & ~Filters.command, liquidity_burned)],
            BUY_TAX: [MessageHandler(Filters.text & ~Filters.command, buy_tax)],
            SELL_TAX: [MessageHandler(Filters.text & ~Filters.command, sell_tax)],
            TRANSFER_TAX: [MessageHandler(Filters.text & ~Filters.command, transfer_tax)],
            CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, confirmation)],
            SELECT_TOKEN: [MessageHandler(Filters.text & ~Filters.command, select_token)],
            EDIT_FIELD: [MessageHandler(Filters.text & ~Filters.command, edit_field)],
            UPDATE_FIELD: [MessageHandler(Filters.text & ~Filters.command, update_field)],
            EDIT_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, edit_confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('view', view_tokens))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

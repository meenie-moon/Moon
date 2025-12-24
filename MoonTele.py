import time
import asyncio
import re
import os
import json
from telethon.sync import TelegramClient
from telethon import errors
from telethon.tl.types import InputPeerChannel

from telethon.tl.functions.messages import GetForumTopicsRequest, ForwardMessagesRequest

# --- Rich UI Imports ---
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint

console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    clear_screen()
    banner_text = Text(r"""
  __  __                  _______   _      
 |  \/  |                |__   __| | |     
 | \  / | ___   ___  _ __   | | ___| | ___ 
 | |\/| |/ _ \ / _ \| '_ \  | |/ _ \ |/ _ \
 | |  | | (_) | (_) | | | | | |  __/ |  __/
 |_|  |_|\___/ \___/|_| |_| |_|\___|_|\___|
                                           
      Telegram Automation CLI v2.0
""", style="bold cyan")
    console.print(Panel(banner_text, border_style="blue", expand=False))

class TelegramForwarder:
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient('session_' + phone_number, api_id, api_hash)
        
        # Sets to store unique extracted data
        self.unique_links = set()
        self.unique_domains = set()
        self.unique_ips = set()

    async def _ensure_authorized(self):
        """Helper method to handle connection and authorization including 2FA."""
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone_number)
            try:
                await self.client.sign_in(self.phone_number, input('Enter the code: '))
            except errors.rpcerrorlist.SessionPasswordNeededError:
                password = input('Two-step verification is enabled. Enter your password: ')
                await self.client.sign_in(password=password)

    async def get_dialogs_list(self):
        await self._ensure_authorized()
        return await self.client.get_dialogs()

    async def get_forum_topics(self, chat_id):
        """Fetches topics from a forum supergroup using raw API request."""
        try:
            # Get full entity to check if it's a forum
            entity = await self.client.get_entity(chat_id)
            if not getattr(entity, 'forum', False):
                return None # Not a forum

            # Use raw request since client.get_forum_topics helper might be missing
            from telethon.tl.functions.messages import GetForumTopicsRequest
            
            # Fetch up to 100 recent topics
            result = await self.client(GetForumTopicsRequest(
                peer=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))
            return result.topics
        except Exception as e:
            print(f"Error fetching topics: {e}")
            return None

    def _extract_and_collect_info(self, text):
        if not text:
            return

        # Pattern for IP Address (IPv4) - Stricter to match valid IPs
        ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        
        # Pattern for links with protocol
        link_pattern = r'https?://[^\s\[\]\(\)\{\},<>"\']+'
        
        # Pattern for domain/link
        domain_pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        
        # Find and collect IPs
        self.unique_ips.update(re.findall(ip_pattern, text))
        
        # Find and collect Links
        found_links = re.findall(link_pattern, text)
        self.unique_links.update(found_links)
        
        # Helper to clean and add domain
        def add_domain(d):
            if '.' in d and len(d) > 3 and not re.match(r'^[0-9.]+$', d):
                tld = d.split('.')[-1]
                if tld.isalpha() and len(tld) >= 2:
                    self.unique_domains.add(d.lower())

        # 1. Extract domains from found links
        from urllib.parse import urlparse
        for link in found_links:
            try:
                parsed = urlparse(link)
                if parsed.netloc:
                    domain_part = parsed.netloc.split(':')[0]
                    add_domain(domain_part)
            except:
                pass

        # 2. Extract domains directly from text
        raw_domains = re.findall(domain_pattern, text)
        for domain in raw_domains:
            add_domain(domain)

    async def scrape_messages_to_file(self, source_chat_id, limit=None, topic_id=None, chat_title=None, topic_title=None, file_handle=None):
        await self._ensure_authorized()

        # Sanitize filename helper
        def sanitize(name):
            return "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()

        # Generate filename (only if no file_handle provided)
        safe_chat = sanitize(chat_title) if chat_title else str(source_chat_id)
        display_title = f"{chat_title}{' - ' + topic_title if topic_title else ''}"
        
        if not file_handle:
            filename = f"history_{safe_chat}"
            if topic_title:
                 filename += f"_{sanitize(topic_title)}"
            elif topic_id:
                 filename += f"_topic{topic_id}"
            filename += ".txt"
            print(f"Starting to scrape messages from {display_title} to {filename}...")
        else:
            print(f"Appending messages from {display_title} to merged file...")

        count = 0
        try:
            # Context manager wrapper: if file_handle is passed, use it; else open new file
            from contextlib import nullcontext
            cm = nullcontext(file_handle) if file_handle else open(filename, "w", encoding="utf-8")
            
            with cm as file:
                # If merging, add a header separator for this chat
                if file_handle:
                    file.write(f"\n{'='*50}\nSOURCE: {display_title}\n{'='*50}\n\n")

                # If topic_id is provided, use reply_to argument to filter by topic
                kwargs = {'limit': limit}
                if topic_id:
                    kwargs['reply_to'] = topic_id

                async for message in self.client.iter_messages(source_chat_id, **kwargs):
                    date = message.date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    sender = "Unknown"
                    if message.sender:
                        if hasattr(message.sender, 'title'): 
                            sender = message.sender.title
                        elif hasattr(message.sender, 'first_name'):
                            sender = message.sender.first_name
                            if hasattr(message.sender, 'last_name') and message.sender.last_name:
                                sender += f" {message.sender.last_name}"
                    
                    content = message.text if message.text else "[Media/Non-text content]"
                    
                    file.write(f"[{date}] {sender}: {content}\n")
                    file.write("-" * 50 + "\n")
                    
                    count += 1
                    if count % 100 == 0:
                        print(f"Scraped {count} messages so far...")

            if not file_handle:
                print(f"\nSuccessfully saved {count} messages to {filename}")
            else:
                print(f"Processed {count} messages.")

        except Exception as e:
            print(f"An error occurred while scraping {source_chat_id}: {e}")

    async def extract_data_from_chat(self, source_chat_id, limit=None, topic_id=None, chat_title=None, topic_title=None):
        await self._ensure_authorized()
        print(f"Scanning messages in {source_chat_id}{' (Topic ' + str(topic_id) + ')' if topic_id else ''}...")
        
        count = 0
        try:
            kwargs = {'limit': limit}
            if topic_id:
                kwargs['reply_to'] = topic_id

            async for message in self.client.iter_messages(source_chat_id, **kwargs):
                self._extract_and_collect_info(message.text)
                
                count += 1
                if count % 100 == 0:
                    print(f"Scanned {count} messages...")
                    
            print(f"Finished scanning {count} messages from {source_chat_id}")
        except Exception as e:
            print(f"An error occurred while scanning {source_chat_id}: {e}")

    def save_extracted_data(self):
        print("\nSaving extracted data...")
        with open("links.txt", "w", encoding="utf-8") as f: 
            for link in sorted(self.unique_links): f.write(link + "\n")
        with open("domains.txt", "w", encoding="utf-8") as f: 
            for domain in sorted(self.unique_domains): f.write(domain + "\n")
        with open("ips.txt", "w", encoding="utf-8") as f: 
            for ip in sorted(self.unique_ips): f.write(ip + "\n")
        with open("all_results.txt", "w", encoding="utf-8") as f:
            f.write("LINKS:\n" + "-" * 20 + "\n")
            for link in sorted(self.unique_links): f.write(link + "\n")
            f.write("\nDOMAINS:\n" + "-" * 20 + "\n")
            for domain in sorted(self.unique_domains): f.write(domain + "\n")
            f.write("\nIP ADDRESSES:\n" + "-" * 20 + "\n")
            for ip in sorted(self.unique_ips): f.write(ip + "\n")
                
        print(f"Extracted data saved. Stats: {len(self.unique_links)} links, {len(self.unique_domains)} domains, {len(self.unique_ips)} IPs.")

    async def forward_messages_to_channel(self, source_chat_id, destination_channel_id, keywords, topic_id=None):
        await self._ensure_authorized()

        # Get last message to start checking from
        last_message_id = (await self.client.get_messages(source_chat_id, limit=1))[0].id
        
        print(f"Listening for new messages in {source_chat_id} {'(Topic ' + str(topic_id) + ')' if topic_id else ''}...")

        while True:
            # Get new messages
            messages = await self.client.get_messages(source_chat_id, min_id=last_message_id, limit=None)

            for message in reversed(messages):
                # Filter by topic if specified
                # In forums, reply_to_msg_id of the message points to the topic ID (thread start message)
                if topic_id:
                    if not message.reply_to or message.reply_to.reply_to_msg_id != topic_id:
                        last_message_id = max(last_message_id, message.id)
                        continue

                # Keyword check
                should_forward = False
                if keywords:
                    if message.text and any(keyword in message.text.lower() for keyword in keywords):
                        print(f"Keyword match: {message.text[:30]}...")
                        should_forward = True
                else:
                    should_forward = True

                if should_forward:
                    try:
                        await self.client.send_message(destination_channel_id, message.text)
                        print("Message forwarded")
                    except Exception as e:
                        print(f"Failed to forward: {e}")

                last_message_id = max(last_message_id, message.id)

            await asyncio.sleep(5)

    async def send_custom_message(self, chat_id, text, topic_id=None, chat_title="Unknown", topic_title=None):
        """Sends a custom message to a chat/topic."""
        await self._ensure_authorized()
        try:
            # Use reply_to to send to a specific topic in a forum
            await self.client.send_message(chat_id, text, reply_to=topic_id)
            target_info = f"{chat_title}" + (f" (Topic: {topic_title})" if topic_title else "")
            print(f"✅ Sent to: {target_info}")
            return True
        except Exception as e:
            print(f"❌ Failed to send to {chat_title}: {e}")
            return False

    async def forward_existing_message(self, target_chat_id, message_object, topic_id=None, chat_title="Unknown", topic_title=None, as_forward=False):
        """Forwards a specific message object (or list of objects for albums) to a chat/topic."""
        await self._ensure_authorized()
        try:
            # Mode 1: True Forward (Retains "Forwarded from", Views, etc.)
            if as_forward:
                # 1. Prepare Message IDs and Origin Chat
                if isinstance(message_object, list):
                    msg_ids = [m.id for m in message_object]
                    origin_chat_id = message_object[0].chat_id
                else:
                    msg_ids = [message_object.id]
                    origin_chat_id = message_object.chat_id

                # 2. Get InputPeer for the source chat (Required for Raw API)
                from_peer = await self.client.get_input_entity(origin_chat_id)
                target_peer = await self.client.get_input_entity(target_chat_id)

                # 3. Execute Raw Forward Request (Supports top_msg_id for Topics)
                from telethon.tl.functions.messages import ForwardMessagesRequest
                await self.client(ForwardMessagesRequest(
                    from_peer=from_peer,
                    id=msg_ids,
                    to_peer=target_peer,
                    top_msg_id=topic_id if topic_id else None  # ✅ This fixes the topic targeting!
                ))
                
            # Mode 2: Send as Copy (Clean, no tag)
            else:
                # Check if it's an Album (list of messages)
                if isinstance(message_object, list):
                    # Find caption (usually on the first item or any item with text)
                    caption = None
                    for m in message_object:
                        if m.text:
                            caption = m.text
                            break
                    
                    # Send as Album
                    await self.client.send_message(
                        target_chat_id, 
                        message=caption, 
                        file=message_object, 
                        reply_to=topic_id
                    )
                else:
                    # Single Message
                    await self.client.send_message(target_chat_id, message_object, reply_to=topic_id)
                
            target_info = f"{chat_title}" + (f" (Topic: {topic_title})" if topic_title else "")
            mode_str = "Forwarded" if as_forward else "Sent Copy"
            print(f"✅ {mode_str} to: {target_info}")
            return True
        except Exception as e:
            print(f"❌ Failed to process {chat_title}: {e}")
            return False


# --- UI Helpers & Template Management ---

# --- Storage Constants ---
CREDENTIALS_FILE = "credentials.txt"
ACCOUNTS_FILE = "accounts.json"
TEMPLATE_FILE = "target_templates.json"

# --- Account Management Helpers ---

def load_accounts():
    """
    Loads accounts from JSON. 
    Migrates from credentials.txt if JSON is missing but txt exists.
    """
    accounts = []
    
    # 1. Try to load from JSON
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
        except Exception as e:
            print(f"Error loading accounts.json: {e}")
    
    # 2. Migration: If JSON is empty/missing but credentials.txt exists
    if not accounts and os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as file:
                lines = file.readlines()
                if len(lines) >= 3:
                    api_id = lines[0].strip()
                    api_hash = lines[1].strip()
                    phone = lines[2].strip()
                    
                    migrated_account = {
                        "phone": phone,
                        "api_id": api_id,
                        "api_hash": api_hash,
                        "name": f"Account {phone}"
                    }
                    accounts.append(migrated_account)
                    save_accounts(accounts)
                    print("✅ Successfully migrated old credentials to accounts.json")
        except Exception as e:
            print(f"Migration failed: {e}")

    return accounts

def save_accounts(accounts):
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=4)
    except Exception as e:
        print(f"Error saving accounts: {e}")

def add_account_interactive(accounts):
    print("\n=== ADD NEW ACCOUNT ===")
    print("Please provide Telegram API credentials.")
    print("Get them from: https://my.telegram.org/auth")
    
    api_id = input("API ID: ").strip()
    api_hash = input("API Hash: ").strip()
    phone = input("Phone Number (International format, e.g. 628xxx): ").strip()
    name = input("Account Label (e.g. My Personal): ").strip()
    
    if not name: name = f"Account {phone}"
    
    # Check duplicate
    for acc in accounts:
        if acc['phone'] == phone:
            print("⚠️ Account with this phone number already exists!")
            return accounts
    
    new_acc = {
        "phone": phone,
        "api_id": api_id,
        "api_hash": api_hash,
        "name": name
    }
    
    accounts.append(new_acc)
    save_accounts(accounts)
    print(f"✅ Account '{name}' added successfully!")
    return accounts

# --- Template Management Helpers ---

def load_templates(account_phone):
    """
    Loads templates specific to the given account phone number.
    Handles migration from old flat format to new nested format.
    """
    if not os.path.exists(TEMPLATE_FILE):
        return {}
    
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data:
            return {}

        # --- Migration Check ---
        # Check if the data is in the old format (values are lists, not dicts)
        # Old format: {"TemplateName": [...]}
        # New format: {"628123...": {"TemplateName": [...]}, "628999...": {...}}
        
        is_old_format = False
        first_value = next(iter(data.values()))
        if isinstance(first_value, list):
            is_old_format = True

        if is_old_format:
            print(f"⚠️ Detected legacy template format. Migrating templates to account: {account_phone}...")
            # Create new structure with current data assigned to this phone
            new_structure = {account_phone: data}
            
            # Save immediately to convert file
            try:
                with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_structure, f, indent=4, ensure_ascii=False)
                print("✅ Migration successful.")
                return data # Return the templates for this user
            except Exception as e:
                print(f"❌ Migration failed: {e}")
                return {} # Fallback
        
        # New Format: Return specifically for this phone, or empty dict if new user
        return data.get(account_phone, {})

    except Exception as e:
        print(f"Error loading templates: {e}")
        return {}

def save_templates(current_account_templates, account_phone):
    """
    Saves templates for a specific account, preserving other accounts' data.
    """
    # 1. Load ALL data first (to not lose other accounts)
    full_data = {}
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                content = json.load(f)
                # Ensure we are working with the new format structure
                # (load_templates handles migration, but raw read might see old format if not loaded yet)
                # But typically load_templates is called before save, so migration happens there.
                # Just to be safe, if we see list values, we assume it's legacy and we are overwriting/migrating now.
                if content and isinstance(next(iter(content.values())), list):
                    # If file is still old format (edge case), we treat it as empty or belongs to current?
                    # Ideally migration happens on load.
                    full_data = {account_phone: current_account_templates}
                else:
                    full_data = content
        except:
            full_data = {}

    # 2. Update specific account
    full_data[account_phone] = current_account_templates

    # 3. Write back
    try:
        with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=4, ensure_ascii=False)
        print("💾 Templates saved successfully.")
    except Exception as e:
        print(f"Error saving templates: {e}")

async def select_topic_interactive(forwarder, chat_id):
    """
    Checks if chat has topics. If so, lets user choose one.
    Returns: (topic_id, topic_title) or (None, None)
    """
    with console.status("[bold green]Fetching forum topics...[/bold green]", spinner="dots"):
        topics = await forwarder.get_forum_topics(chat_id)
    
    if not topics:
        return None, None # Not a forum or no topics

    console.print(Panel("This group is a [bold]Forum[/bold]. Please select a specific topic.", title="Select Topic", border_style="cyan"))

    table = Table(box=None, padding=(0,1))
    table.add_column("No", justify="right", style="cyan")
    table.add_column("Topic Title", style="white")
    table.add_column("ID", style="dim")

    topic_list = []
    index = 1
    for t in topics:
        # Skip deleted topics or those without title
        if not hasattr(t, 'title'):
            continue
            
        topic_list.append(t)
        table.add_row(str(index), t.title, str(t.id))
        index += 1

    console.print(table)
    console.print("[0] All Topics (Entire Group)", style="bold green")
    
    while True:
        try:
            choice_str = console.input(f"[bold yellow]❯ Enter choice (0-{len(topic_list)}): [/bold yellow]")
            choice = int(choice_str)
            
            if choice == 0:
                console.print("[green]✅ Selected: All Topics[/green]")
                return None, None
            if 1 <= choice <= len(topic_list):
                selected = topic_list[choice-1]
                console.print(f"[green]✅ Selected Topic: {selected.title}[/green]")
                return selected.id, selected.title
            console.print("[red]❌ Invalid number.[/red]")
        except ValueError:
            console.print("[red]❌ Invalid input.[/red]")

async def select_chat_interactive(forwarder, prompt_text="Select a chat", allow_all=False):
    """
    Returns: (chat_id, chat_title, topic_id, topic_title)
    """
    print_banner()
    console.print(f"[bold cyan]--- {prompt_text} ---[/bold cyan]")
    
    with console.status("[bold green]Fetching chat list...[/bold green]", spinner="dots"):
        dialogs = await forwarder.get_dialogs_list()
    
    if not dialogs:
        console.print("[bold red]❌ No chats found.[/bold red]")
        time.sleep(1)
        return None, None, None, None

    # Create Table
    table = Table(box=None, padding=(0,1))
    table.add_column("No", justify="right", style="cyan")
    table.add_column("Chat Title", style="white")
    table.add_column("ID", style="dim")
    table.add_column("Type", style="yellow")

    for i, dialog in enumerate(dialogs, 1):
        d_type = "Forum" if getattr(dialog.entity, 'forum', False) else ("Group" if dialog.is_group else "Channel" if dialog.is_channel else "User")
        table.add_row(str(i), dialog.title, str(dialog.id), d_type)

    console.print(table)
    
    if allow_all:
        console.print("[0] All Chats", style="bold green")

    while True:
        try:
            prompt = f"[bold yellow]❯ Enter choice (0-{len(dialogs)}): [/bold yellow]" if allow_all else f"[bold yellow]❯ Enter choice (1-{len(dialogs)}): [/bold yellow]"
            choice_str = console.input(prompt)
            choice = int(choice_str)

            if allow_all and choice == 0:
                return 0, "All Chats", None, None
            
            if 1 <= choice <= len(dialogs):
                selected = dialogs[choice-1]
                console.print(f"[green]✅ Selected Chat: {selected.title}[/green]")
                
                # Check for topics
                topic_id = None
                topic_title = None
                if getattr(selected.entity, 'forum', False):
                    topic_id, topic_title = await select_topic_interactive(forwarder, selected.id)

                return selected.id, selected.title, topic_id, topic_title
            else:
                console.print("[red]❌ Invalid number.[/red]")
        except ValueError:
            console.print("[red]❌ Invalid input.[/red]")

async def manage_templates(forwarder, account_phone):
    while True:
        templates = load_templates(account_phone)
        print_banner()
        console.print(f"[bold cyan]📁 MANAGE TEMPLATES ({account_phone})[/bold cyan]\n")
        
        console.print(Panel("[1] View Templates       [2] Create New Template\n[3] Edit Template        [4] Delete Template\n[5] Back to Main Menu", title="Actions", border_style="blue"))
        
        choice = console.input("[bold yellow]❯ Enter choice: [/bold yellow]")
        
        if choice == "1":
            if not templates:
                console.print("[yellow]⚠️ No templates found for this account.[/yellow]")
                time.sleep(1)
                continue
            
            # List Templates
            table = Table(title="Available Templates", box=None)
            table.add_column("No", style="cyan", justify="right")
            table.add_column("Template Name", style="white")
            table.add_column("Target Count", style="green")
            
            keys = list(templates.keys())
            for i, key in enumerate(keys, 1):
                table.add_row(str(i), key, str(len(templates[key])))
            console.print(table)
            
            try:
                idx = int(console.input("Select template to view (0 to cancel): "))
                if idx > 0 and idx <= len(keys):
                    name = keys[idx-1]
                    
                    # Show Template Contents
                    content_table = Table(title=f"Contents of '{name}'", box=None)
                    content_table.add_column("No", style="cyan", justify="right")
                    content_table.add_column("Group Name", style="white")
                    content_table.add_column("Topic", style="yellow")
                    
                    for j, item in enumerate(templates[name], 1):
                        topic_display = item['topic_title'] if item.get('topic_title') else (f"ID: {item['topic_id']}" if item.get('topic_id') else "All/None")
                        content_table.add_row(str(j), item['chat_title'][:40], str(topic_display))
                    
                    console.print(content_table)
                    console.input("\n[dim]Press Enter to continue...[/dim]")
            except ValueError:
                pass

        elif choice == "2":
            name = console.input("Enter new template name: ").strip()
            if not name: continue
            if name in templates:
                console.print("[yellow]⚠️ Template already exists![/yellow]")
                if not Confirm.ask("Overwrite?"): continue
            
            new_targets = []
            while True:
                cid, ctitle, tid, ttitle = await select_chat_interactive(forwarder, f"Add target to '{name}' (Cancel/0 to finish)")
                if cid is None:
                    console.print("Selection finished.")
                    break
                
                new_targets.append({
                    "chat_id": cid,
                    "chat_title": ctitle,
                    "topic_id": tid,
                    "topic_title": ttitle
                })
                console.print(f"[green]✅ Added {ctitle}[/green]")
                
                if not Confirm.ask("Add another target to this template?"):
                    break
            
            if new_targets:
                templates[name] = new_targets
                save_templates(templates, account_phone)
                console.print(f"[green]✅ Template '{name}' created with {len(new_targets)} targets.[/green]")
                time.sleep(1)
            else:
                console.print("[yellow]⚠️ Template creation cancelled.[/yellow]")
                time.sleep(1)

        elif choice == "3":
            if not templates:
                console.print("[yellow]⚠️ No templates to edit.[/yellow]")
                time.sleep(1)
                continue
                
            keys = list(templates.keys())
            # List Templates for Edit
            table = Table(title="Select Template to Edit", box=None)
            table.add_column("No", style="cyan")
            table.add_column("Name", style="white")
            for i, key in enumerate(keys, 1):
                table.add_row(str(i), key)
            console.print(table)
            
            try:
                idx = int(console.input("Select template (0 to cancel): "))
                if idx <= 0 or idx > len(keys): continue
                
                target_name = keys[idx-1]
                current_items = templates[target_name]
                
                console.print(f"\n[bold cyan]Editing: {target_name}[/bold cyan]")
                console.print("[1] Add new target\n[2] Remove existing target")
                sub_choice = console.input("[bold yellow]❯ Choose action: [/bold yellow]")
                
                if sub_choice == "1":
                    cid, ctitle, tid, ttitle = await select_chat_interactive(forwarder, "Select Chat to Add")
                    if cid:
                        current_items.append({
                            "chat_id": cid,
                            "chat_title": ctitle,
                            "topic_id": tid,
                            "topic_title": ttitle
                        })
                        console.print("[green]✅ Item added.[/green]")
                        save_templates(templates, account_phone)
                        time.sleep(1)
                        
                elif sub_choice == "2":
                    # Show items to remove
                    ctable = Table(box=None)
                    ctable.add_column("No", style="cyan")
                    ctable.add_column("Name", style="white")
                    for j, item in enumerate(current_items, 1):
                        ctable.add_row(str(j), item['chat_title'])
                    console.print(ctable)
                    
                    rm_idx = int(console.input("Enter number to remove (0 to cancel): "))
                    if 1 <= rm_idx <= len(current_items):
                        removed = current_items.pop(rm_idx-1)
                        console.print(f"[green]🗑️ Removed: {removed['chat_title']}[/green]")
                        save_templates(templates, account_phone)
                        time.sleep(1)
            except ValueError:
                console.print("[red]Invalid input[/red]")
                time.sleep(1)

        elif choice == "4":
            if not templates:
                console.print("[yellow]⚠️ No templates to delete.[/yellow]")
                time.sleep(1)
                continue
            
            keys = list(templates.keys())
            for i, key in enumerate(keys, 1):
                console.print(f"{i}. {key}")
                
            try:
                idx = int(console.input("Select template to delete (0 to cancel): "))
                if idx > 0 and idx <= len(keys):
                    del_key = keys[idx-1]
                    if Confirm.ask(f"Are you sure you want to delete '{del_key}'?"):
                        del templates[del_key]
                        save_templates(templates, account_phone)
                        console.print("[green]🗑️ Template deleted.[/green]")
                        time.sleep(1)
            except ValueError:
                pass

        elif choice == "5":
            break

async def manage_accounts_menu(accounts, current_account):
    """
    UI for managing accounts.
    Returns: (updated_accounts_list, account_to_switch_to_or_None)
    """
    while True:
        print_banner()
        
        # Prepare Account Table
        table = Table(title="👥 Registered Accounts", box=None)
        table.add_column("No", style="cyan", justify="right")
        table.add_column("Name", style="white")
        table.add_column("Phone", style="green")
        table.add_column("Status", style="bold yellow")

        for i, acc in enumerate(accounts, 1):
            status = "✅ Active" if acc == current_account else ""
            display_info = acc.get('real_name', acc['name'])
            table.add_row(str(i), display_info, acc['phone'], status)

        console.print(table)
        console.print(Panel("[1] List All (Refresh)   [2] Add New Account\n[3] Switch Account       [4] Delete Account\n[5] Back to Main Menu", title="Actions", border_style="blue"))
        
        choice = console.input("[bold yellow]❯ Enter choice: [/bold yellow]")
        
        if choice == "1":
            # Just loop to refresh
            pass

        elif choice == "2":
            accounts = add_account_interactive(accounts)

        elif choice == "3":
            console.print("\n[bold cyan]🔄 Switch Account[/bold cyan]")
            try:
                idx = int(console.input("Select account number (0 to cancel): "))
                if 1 <= idx <= len(accounts):
                    new_active = accounts[idx-1]
                    if new_active == current_account:
                        console.print("[yellow]⚠️ You are already logged in to this account.[/yellow]")
                        time.sleep(1)
                    else:
                        console.print(f"[green]🔄 Switching to {new_active['name']}...[/green]")
                        time.sleep(1)
                        return accounts, new_active
            except ValueError:
                pass

        elif choice == "4":
            console.print("\n[bold red]🗑️ Delete Account[/bold red]")
            try:
                idx = int(console.input("Select account number to DELETE (0 to cancel): "))
                if 1 <= idx <= len(accounts):
                    target = accounts[idx-1]
                    if target == current_account:
                        console.print("[red]⚠️ Cannot delete the currently active account! Switch first.[/red]")
                        time.sleep(2)
                    else:
                        if Confirm.ask(f"Are you sure you want to DELETE [bold red]{target['name']}[/bold red]?"):
                            accounts.pop(idx-1)
                            save_accounts(accounts)
                            console.print("[green]🗑️ Account deleted.[/green]")
                            time.sleep(1)
            except ValueError:
                pass
                
        elif choice == "5":
            return accounts, None

async def main():
    print("\n=== Telegram Automation Tool ===\n")
    
    # 1. Load Accounts
    accounts = load_accounts()

    # 2. Initial Setup if no accounts exist
    if not accounts:
        print("\n=== PENGATURAN AWAL: KREDENSIAL TELEGRAM ===")
        print("Belum ada akun yang tersimpan. Silakan tambahkan akun pertama Anda.")
        print("Dapatkan API ID & Hash di: https://my.telegram.org/auth")
        print("================================================")
        accounts = add_account_interactive(accounts)
        if not accounts:
            print("❌ Setup cancelled. Exiting.")
            return

    # 3. Set Active Account (Default to first one)
    active_account = accounts[0]
    
    # --- OUTER LOOP: Application Lifecycle (handles account switching) ---
    while True:
        print(f"\n🔑 Logging in as: {active_account['name']} ({active_account['phone']})...")
        
        # Initialize Client
        forwarder = TelegramForwarder(
            active_account['api_id'], 
            active_account['api_hash'], 
            active_account['phone']
        )
        
        try:
            await forwarder._ensure_authorized()
            
            # --- Fetch User Info & Update Storage ---
            me = await forwarder.client.get_me()
            tg_name = f"{me.first_name} {me.last_name or ''}".strip()
            if me.username:
                tg_name += f" (@{me.username})"
            
            print(f"✅ Connected as: {tg_name}")
            
            # Update info in memory and file
            active_account['real_name'] = tg_name
            for acc in accounts:
                if acc['phone'] == active_account['phone']:
                    acc['real_name'] = tg_name
            save_accounts(accounts)
            # ----------------------------------------

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("Check your internet or credentials.")
            # Option to retry or exit? let's loop back to manage menu conceptually, 
            # but simplest is to just break or allow user to fix via menu if possible?
            # If auth fails, we can't really enter the main menu safely. 
            # Let's ask user.
            retry = input("Try again? (y/n) or 'm' for manage accounts: ")
            if retry.lower() == 'm':
                accounts, new_acc = await manage_accounts_menu(accounts, active_account)
                if new_acc:
                    active_account = new_acc
                continue
            elif retry.lower() == 'y':
                continue
            else:
                break

        # --- INNER LOOP: Main Menu for current account ---
        switch_requested = False
        while True:
            print_banner()
            
            # Use real name for display if available
            menu_title = active_account.get('real_name', active_account['name'])
            
            # Create Menu Table
            menu_table = Table(show_header=False, box=None, padding=(0, 2))
            menu_table.add_column("Option", justify="right", style="cyan bold")
            menu_table.add_column("Description", justify="left")
            
            menu_table.add_row("[1]", "📂 List Chats")
            menu_table.add_row("[2]", "🔄 Forward Messages (Real-time)")
            menu_table.add_row("[3]", "💾 Scrape Past Messages")
            menu_table.add_row("[4]", "🔍 Extract Data (Links/IPs)")
            menu_table.add_row("[5]", "📝 Manage Target Templates")
            menu_table.add_row("[6]", "🚀 Send Message / Broadcast")
            menu_table.add_row("[7]", "👥 Manage Accounts")
            menu_table.add_row("[8]", "🚪 Exit")

            # Display Info Panel
            info_text = Text(f"Active Account: {menu_title}\nPhone: {active_account['phone']}", style="green")
            console.print(Panel(info_text, title="[bold]Status[/bold]", border_style="green"))
            console.print(menu_table)
            console.print(Panel("Select an option by entering the corresponding number.", style="dim"))
            
            choice = console.input("[bold yellow]❯ Enter choice: [/bold yellow]")
            
            if choice == "1":
                dialogs = await forwarder.get_dialogs_list()
                if dialogs:
                    # Save to file
                    with open(f"chats_of_{active_account['phone']}.txt", "w", encoding="utf-8") as f:
                        for d in dialogs: f.write(f"ID: {d.id}, Title: {d.title}\n")
                    
                    # Create Rich Table
                    table = Table(title=f"Chat List ({len(dialogs)} items)", box=None, padding=(0,1))
                    table.add_column("No", justify="right", style="cyan")
                    table.add_column("Chat Title", style="white")
                    table.add_column("ID", style="dim")
                    table.add_column("Type", style="yellow")

                    for i, dialog in enumerate(dialogs, 1):
                        d_type = "Forum" if getattr(dialog.entity, 'forum', False) else ("Group" if dialog.is_group else "Channel" if dialog.is_channel else "User")
                        table.add_row(str(i), dialog.title, str(dialog.id), d_type)

                    console.print(table)
                    print(f"\n✅ List saved to 'chats_of_{active_account['phone']}.txt'")
                    console.input("\n[dim]Press Enter to continue...[/dim]") # Tambahkan jeda di sini

            elif choice == "2":
                source_id, source_title, topic_id, topic_title = await select_chat_interactive(forwarder, "Select SOURCE Chat")
                if source_id is None: continue
                
                dest_id, dest_title, _, _ = await select_chat_interactive(forwarder, "Select DESTINATION Channel")
                if dest_id is None: continue

                k_input = input("Keywords (comma separated, or blank): ")
                keywords = [k.strip() for k in k_input.split(",")] if k_input.strip() else []
                
                print(f"\n🚀 Forwarding: {source_title} -> {dest_title}")
                try:
                    await forwarder.forward_messages_to_channel(source_id, dest_id, keywords, topic_id)
                except KeyboardInterrupt:
                    print("\nStopped.")

            elif choice == "3":
                # Reuse existing scrape logic structure
                print("\n--- Scrape Messages ---")
                print("1. Single Chat")
                print("2. All Chats")
                print("3. From Template")
                sub_choice = input("Select source type: ")
                
                targets = []
                if sub_choice == "1":
                    cid, ctitle, tid, ttitle = await select_chat_interactive(forwarder, "Select Chat")
                    if cid: targets.append({'id': cid, 'title': ctitle, 'topic_id': tid, 'topic_title': ttitle})
                elif sub_choice == "2":
                    print("Fetching chats...")
                    for d in await forwarder.client.get_dialogs():
                        targets.append({'id': d.id, 'title': d.title, 'topic_id': None, 'topic_title': None})
                elif sub_choice == "3":
                    templates = load_templates(active_account['phone'])
                    if templates:
                        print("Available Templates:", ", ".join(templates.keys()))
                        t_name = input("Enter template name: ")
                        if t_name in templates:
                            for item in templates[t_name]:
                                targets.append({'id': item['chat_id'], 'title': item['chat_title'], 'topic_id': item['topic_id'], 'topic_title': item['topic_title']})

                if not targets:
                    print("❌ No targets.")
                    continue

                limit_input = input("Number of messages (0 for all): ")
                limit = int(limit_input) if limit_input.isdigit() and limit_input != "0" else None
                
                # Check merge
                file_handle = None
                if len(targets) > 1 and input("Merge into one file? (y/n): ").lower() == 'y':
                    fname = input("Filename (default: merged.txt): ") or "merged.txt"
                    file_handle = open(fname, "w", encoding="utf-8")

                print(f"Starting scraping {len(targets)} targets...")
                
                if file_handle:
                    for t in targets:
                        await forwarder.scrape_messages_to_file(t['id'], limit, t.get('topic_id'), chat_title=t['title'], topic_title=t.get('topic_title'), file_handle=file_handle)
                    file_handle.close()
                else:
                    semaphore = asyncio.Semaphore(5)
                    async def safe_scrape(t):
                        async with semaphore:
                            try: await forwarder.scrape_messages_to_file(t['id'], limit, t.get('topic_id'), chat_title=t['title'], topic_title=t.get('topic_title'))
                            except Exception as e: print(f"Err {t['title']}: {e}")
                    await asyncio.gather(*[safe_scrape(t) for t in targets])
                
                print("✅ Done.")

            elif choice == "4":
                # Reuse existing extract logic structure
                print("\n--- Extract Data ---")
                print("1. Single Chat")
                print("2. All Chats")
                print("3. From Template")
                sub_choice = input("Select source type: ")
                
                targets = []
                if sub_choice == "1":
                    cid, ctitle, tid, ttitle = await select_chat_interactive(forwarder, "Select Chat")
                    if cid: targets.append({'id': cid, 'title': ctitle, 'topic_id': tid, 'topic_title': ttitle})
                elif sub_choice == "2":
                    print("Fetching chats...")
                    for d in await forwarder.client.get_dialogs():
                        targets.append({'id': d.id, 'title': d.title, 'topic_id': None, 'topic_title': None})
                elif sub_choice == "3":
                    templates = load_templates(active_account['phone'])
                    if templates:
                        print("Available Templates:", ", ".join(templates.keys()))
                        t_name = input("Enter template name: ")
                        if t_name in templates:
                            for item in templates[t_name]:
                                targets.append({'id': item['chat_id'], 'title': item['chat_title'], 'topic_id': item['topic_id'], 'topic_title': item['topic_title']})

                if targets:
                    limit_input = input("Number of messages (0 for all): ")
                    limit = int(limit_input) if limit_input.isdigit() and limit_input != "0" else None
                    
                    semaphore = asyncio.Semaphore(5)
                    async def safe_extract(t):
                        async with semaphore:
                            try: await forwarder.extract_data_from_chat(t['id'], limit, t.get('topic_id'), chat_title=t['title'], topic_title=t.get('topic_title'))
                            except: pass
                    await asyncio.gather(*[safe_extract(t) for t in targets])
                    forwarder.save_extracted_data()
                else:
                    print("❌ No targets.")

            elif choice == "5":
                await manage_templates(forwarder, active_account['phone'])

            elif choice == "6":
                print_banner()
                console.print(Panel("[1] Single Chat (One time)\n[2] From Template (Bulk)", title="🚀 Broadcast Target Selection", border_style="blue"))
                sub_choice = console.input("[bold yellow]❯ Choice: [/bold yellow]")
                targets = []
                
                if sub_choice == "1":
                    cid, ctitle, tid, ttitle = await select_chat_interactive(forwarder, "Select Target")
                    if cid: targets.append({'id': cid, 'title': ctitle, 'topic_id': tid, 'topic_title': ttitle})
                
                elif sub_choice == "2":
                    templates = load_templates(active_account['phone'])
                    if templates:
                        # Template Table
                        table = Table(title="Available Templates", box=None)
                        table.add_column("No", style="cyan", justify="right")
                        table.add_column("Name", style="white")
                        table.add_column("Targets", style="green")
                        
                        template_keys = list(templates.keys())
                        for i, key in enumerate(template_keys, 1):
                            table.add_row(str(i), key, str(len(templates[key])))
                        console.print(table)
                        
                        try:
                            t_idx_input = console.input("[bold yellow]❯ Enter number of template to use: [/bold yellow]")
                            t_idx = int(t_idx_input)
                            if 1 <= t_idx <= len(template_keys):
                                t_name = template_keys[t_idx-1]
                                for item in templates[t_name]:
                                    targets.append({'id': item['chat_id'], 'title': item['chat_title'], 'topic_id': item['topic_id'], 'topic_title': item['topic_title']})
                                console.print(f"[green]✅ Loaded {len(targets)} targets from '{t_name}'[/green]")
                            else:
                                console.print("[red]❌ Invalid template number.[/red]")
                        except ValueError:
                            console.print("[red]❌ Invalid input.[/red]")
                    else:
                        console.print("[yellow]⚠️ No templates found for this account.[/yellow]")
                
                if targets:
                    console.print(Panel("[1] Manual Input (Type here)\n[2] Read from File (.txt)\n[3] Forward Message (Recommended)", title="Select Message Source", border_style="blue"))
                    msg_choice = console.input("[bold yellow]❯ Select source: [/bold yellow]")
                    
                    message_text = None
                    message_object = None
                    
                    if msg_choice == "1":
                        console.print("[cyan]Enter your message (press Enter twice to finish):[/cyan]")
                        lines = []
                        while True:
                            line = input()
                            if not line: break
                            lines.append(line)
                        message_text = "\n".join(lines)
                    
                    elif msg_choice == "2":
                        fname = console.input("[bold yellow]Enter filename (e.g. ad.txt): [/bold yellow]")
                        try:
                            with open(fname, 'r', encoding='utf-8') as f:
                                message_text = f.read()
                            console.print(f"[green]✅ Loaded {len(message_text)} chars from file.[/green]")
                        except Exception as e:
                            console.print(f"[red]❌ Error reading file: {e}[/red]")
                    
                    elif msg_choice == "3":
                        console.print(Panel("""[bold]Instruksi Forward Pesan[/bold]
1. Salin tautan/link pesan Telegram yang ingin diteruskan.
2. Dukungan: Teks, Foto, Video, Album, dan File.
3. Contoh Link: https://t.me/channel_name/1234""", border_style="cyan"))
                        
                        link = console.input("[bold yellow]❯ Masukkan Link Pesan: [/bold yellow]").strip()
                        try:
                            if "t.me/" not in link:
                                console.print("[red]❌ Invalid link format.[/red]")
                            else:
                                link = link.split("?")[0]
                                parts = link.split("/")
                                msg_id = int(parts[-1])
                                
                                chat_identifier = None
                                if "/c/" in link:
                                    try:
                                        c_index = parts.index("c")
                                        raw_id = parts[c_index + 1]
                                        chat_identifier = int(f"-100{raw_id}")
                                    except: pass
                                else:
                                    t_index = parts.index("t.me")
                                    chat_identifier = parts[t_index + 1]
                                
                                if chat_identifier:
                                    print(f"🔄 Fetching message {msg_id}...")
                                    # Fetch primary message
                                    primary_msg = await forwarder.client.get_messages(chat_identifier, ids=msg_id)
                                    
                                    if not primary_msg:
                                        print("❌ Message not found or access denied.")
                                        message_object = None
                                    else:
                                        # Check for Album (Grouped Media)
                                        if primary_msg.grouped_id:
                                            print(f"📦 Detected Album (ID: {primary_msg.grouped_id}). Fetching all parts...")
                                            # Fetch surrounding messages to find the rest of the album
                                            # Albums are usually consecutive, scanning +/- 9 IDs should cover it (max album size is 10)
                                            surrounding_ids = list(range(msg_id - 9, msg_id + 10))
                                            msgs = await forwarder.client.get_messages(chat_identifier, ids=surrounding_ids)
                                            
                                            # Filter messages belonging to the same group
                                            album_messages = [m for m in msgs if m and m.grouped_id == primary_msg.grouped_id]
                                            album_messages.sort(key=lambda x: x.id)
                                            
                                            if album_messages:
                                                message_object = album_messages
                                                print(f"✅ Album fetched: {len(album_messages)} items.")
                                            else:
                                                message_object = primary_msg
                                                print("⚠️ Failed to group album, using single message.")
                                        else:
                                            # Single Message
                                            message_object = primary_msg
                                            print("✅ Message fetched successfully!")
                                else:
                                    print("❌ Could not parse chat ID.")
                        except Exception as e:
                            print(f"❌ Error: {e}")

                    if not message_text and not message_object:
                        console.print("[red]❌ No valid message to send.[/red]")
                    else:
                        # --- Mode Selection (Only for Message Objects/Links) ---
                        send_as_forward = False
                        if message_object:
                            console.print(Panel("[1] Send as Copy (Clean, No Tag)\n[2] Forward (With Tag & Views, Trusted)", title="Forwarding Mode", border_style="cyan"))
                            mode_input = console.input("[bold yellow]❯ Select Mode (Default 1): [/bold yellow]")
                            if mode_input == "2":
                                send_as_forward = True
                                console.print("[green]✅ Mode: True Forward (Tag enabled)[/green]")
                            else:
                                console.print("[green]✅ Mode: Send as Copy (Clean)[/green]")
                        
                        console.print(f"\n[green]🚀 Ready to send to {len(targets)} targets.[/green]")
                        
                        console.print(Panel("""[bold white]Delay Settings[/bold white]
Set a delay between messages to avoid spam detection.
[yellow]Recommended: 3-5 seconds[/yellow]""", border_style="yellow"))
                        
                        delay_input = console.input("[bold yellow]   Enter delay (seconds) [Default: 5]: [/bold yellow]")
                        try:
                            delay = float(delay_input) if delay_input else 5.0
                        except ValueError:
                            delay = 5.0
                        
                        console.print(f"[green]✅ Using delay: {delay}s[/green]")

                        if Confirm.ask("Start Broadcast?", default=True):
                            print_banner()
                            console.print(f"[bold cyan]🚀 Broadcasting to {len(targets)} targets...[/bold cyan]\n")
                            
                            with Progress(
                                SpinnerColumn(),
                                TextColumn("[progress.description]{task.description}"),
                                BarColumn(),
                                TaskProgressColumn(),
                                console=console
                            ) as progress:
                                task_id = progress.add_task("[cyan]Starting...", total=len(targets))
                                
                                for i, t in enumerate(targets, 1):
                                    chat_name = t['title'][:30]
                                    progress.update(task_id, description=f"[cyan]Sending to {chat_name}...")
                                    
                                    if message_object:
                                        await forwarder.forward_existing_message(
                                            t['id'], message_object, 
                                            topic_id=t.get('topic_id'), 
                                            chat_title=t['title'], 
                                            topic_title=t.get('topic_title'),
                                            as_forward=send_as_forward
                                        )
                                    else:
                                        await forwarder.send_custom_message(
                                            t['id'], message_text, 
                                            topic_id=t.get('topic_id'), 
                                            chat_title=t['title'], 
                                            topic_title=t.get('topic_title')
                                        )
                                    
                                    # Update progress
                                    progress.advance(task_id)
                                    await asyncio.sleep(delay)
                                
                            console.print("\n[bold green]✅ Broadcast complete![/bold green]")
                            time.sleep(2)
                        else:
                            console.print("[yellow]Cancelled.[/yellow]")
                else:
                    print("❌ No targets.")

            elif choice == "7":
                accounts, new_acc = await manage_accounts_menu(accounts, active_account)
                if new_acc:
                    # User requested to switch
                    print(f"👋 Disconnecting {active_account['name']}...")
                    await forwarder.client.disconnect()
                    active_account = new_acc
                    switch_requested = True
                    break # Break inner loop to restart outer loop with new account

            elif choice == "8":
                print("👋 Exiting...")
                await forwarder.client.disconnect()
                return

            else:
                print("Invalid choice")
        
        if not switch_requested:
            # If inner loop broke but not for switch (e.g. error), exit outer too
            break

if __name__ == "__main__":
    asyncio.run(main())
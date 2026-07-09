"""Seed development data for dashboard testing."""

import random
from datetime import UTC, datetime, timedelta

from core.models import DisplayDevice, Settings
from django.core.management.base import BaseCommand
from participants.models import Participant
from paws_on_stream_web.factories import UserFactory
from streaming.models import Event, Message

FURRY_NAMES = [
    "FrostPaw",
    "LunaTail",
    "ShadowWolf",
    "BerryFox",
    "ThunderPurr",
    "MochiCat",
    "StormHawk",
    "PixelPaw",
    "MapleLeaf",
    "EchoFur",
    "NebulaPaws",
    "CopperTail",
    "WillowPaw",
    "SparkFox",
    "AsterWolf",
    "MistyPaw",
    "JadeTail",
    "BlazeFur",
    "SilverPaw",
    "CedarFox",
]

MESSAGES_TEXT = [
    "Hey everyone! 🐾",
    "Who's going to the panel at 3pm?",
    "Just arrived, this place is amazing!",
    "Can someone point me to the vendor hall?",
    "Furry convention vibes are unmatched ✨",
    "Is there WiFi? My phone keeps disconnecting",
    "Looking for my fur-family, meet at the main stage!",
    "The art show is incredible this year!",
    "Anyone want to grab food later?",
    "This convention is worth every penny 💰",
    "First time here, feeling a bit nervous 😅",
    "The DJ last night was fire 🔥",
    "Does anyone have a charger I can borrow?",
    "Fursona photos with anyone? 📸",
    "The food court has the best ramen I've ever had 🍜",
    "Just finished the workshop, learned so much!",
    "The cosplay contest is going to be epic",
    "Who else is here for the midnight furball?",
    "Already made new friends, this is awesome!",
    "The venue is bigger than I expected 🤩",
]

PHOTO_CAPTIONS = [
    "Check out the view from the balcony!",
    "The food looks amazing 🍕",
    "First look at the venue!",
    "Group photo time!",
    "The art show setup is incredible",
    "Sunset from the rooftop 🌅",
    "My fursona just arrived!",
    "The welcome banner is huge!",
]

STICKER_EMOJIS = [
    "🐾",
    "🦊",
    "🐺",
    "🐱",
    "🐶",
    "🦌",
    "✨",
    "🔥",
    "💖",
    "🎉",
    "🎭",
    "🐲",
]


class Command(BaseCommand):
    help = "Seed development data for dashboard testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data first",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of messages to create",
        )

    def handle(self, *args, **options):
        now = datetime.now(tz=UTC)

        if options["clear"]:
            self.stdout.write("🧹 Clearing existing data...")
            Message.objects.all().delete()
            DisplayDevice.objects.all().delete()
            Settings.objects.all().delete()
            Event.objects.all().delete()
            Participant.objects.all().delete()
            # Clear users too (needed for approved_by FK + unique username)
            from django.contrib.auth.models import User as AuthUser

            AuthUser.objects.filter(username="moderator").delete()

        # --- Settings ---
        Settings.objects.get_or_create(
            id=1,
            defaults={
                "bot_status": "online",
                "display_duration_sec": 8,
                "auto_approve": False,
            },
        )

        # --- User (für approved_by) ---
        mod_user = UserFactory(username="moderator", first_name="Lurky")
        self.stdout.write(f"👤 Created user: {mod_user.username}")

        # --- Events ---
        active_event = Event.objects.create(
            name="Main Stage",
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
            is_active=True,
        )

        Event.objects.create(
            name="Workshop A",
            starts_at=now - timedelta(hours=3),
            ends_at=now - timedelta(hours=1),
            is_active=False,
        )

        Event.objects.create(
            name="Night Party",
            starts_at=now + timedelta(hours=5),
            ends_at=now + timedelta(hours=8),
            is_active=False,
        )
        self.stdout.write("📅 Created 3 events (1 active)")

        # --- Participants ---
        participants = []
        for i, name in enumerate(FURRY_NAMES):
            banned = i < 2
            muted = 2 <= i < 5
            participants.append(
                Participant.objects.create(
                    telegram_id=9_000_000_000 + i,
                    display_name=name,
                    banned=banned,
                    muted_until=(now + timedelta(minutes=30)) if muted else None,
                )
            )
        self.stdout.write(
            f"🐾 Created {len(participants)} participants (2 banned, 3 muted)"
        )

        # --- Messages ---
        statuses = (
            ["pending"] * 15 + ["approved"] * 20 + ["rejected"] * 10 + ["displayed"] * 5
        )
        random.shuffle(statuses)

        media_types = ["text"] * 35 + ["photo"] * 8 + ["gif"] * 5 + ["sticker"] * 2

        messages_created = 0
        for i, status in enumerate(statuses[: options["count"]]):
            offset = random.randint(0, 60) * 60  # 0-60 min ago
            created = now - timedelta(seconds=offset)

            participant = random.choice(participants)
            media_type = media_types[i % len(media_types)]

            # Media-Content je nach Typ
            content, media_url, emoji = self._random_message_content(media_type)

            Message.objects.create(
                participant=participant,
                event=active_event if random.random() > 0.2 else None,
                content=content,
                media_type=media_type,
                media_url=media_url,
                sticker_emoji=emoji,
                status=status,
                created_at=created,
                approved_by=mod_user if status in ("approved", "displayed") else None,
                approved_at=(created + timedelta(seconds=5))
                if status in ("approved", "displayed")
                else None,
            )
            messages_created += 1

        self.stdout.write(f"✉️  Created {messages_created} messages")
        self.stdout.write(
            f"   Pending: {Message.objects.filter(status='pending').count()}"
        )

        # --- DisplayDevices ---
        DisplayDevice.objects.create(
            device_id="pi-01",
            hostname="display-main.local",
            last_seen=now - timedelta(seconds=5),
        )
        DisplayDevice.objects.create(
            device_id="pi-02",
            hostname="display-workshop.local",
            last_seen=now - timedelta(seconds=20),
        )
        DisplayDevice.objects.create(
            device_id="pi-03",
            hostname="display-backup.local",
            last_seen=now - timedelta(minutes=5),
        )
        self.stdout.write("📺 Created 3 display devices")

        self.stdout.write(self.style.SUCCESS("✅ Seed complete!"))

    @staticmethod
    def _random_message_content(media_type):
        """Return (content, media_url, sticker_emoji) based on media_type."""
        if media_type == "photo":
            return (
                random.choice(PHOTO_CAPTIONS),
                f"https://i.ibb.co/photo/{random.randint(100000, 999999)}.jpg",
                "",
            )
        if media_type == "gif":
            return (
                "",
                f"https://media.giphy.com/media/{random.randint(10000, 99999)}.gif",
                "",
            )
        if media_type == "sticker":
            return (
                "",
                f"https://i.ibb.co/sticker/{random.randint(100000, 999999)}.webp",
                random.choice(STICKER_EMOJIS),
            )
        # text
        return random.choice(MESSAGES_TEXT), "", ""

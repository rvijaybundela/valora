from flask import (
    Flask,
    request,
    redirect,
    url_for,
    flash,
    render_template_string,
    jsonify
)

from datetime import datetime, timedelta
from pathlib import Path
import os
import json
import re
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import requests
import resend

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "unisex-salon-secret-key"
)

POCKETBASE_URL = os.getenv(
    "POCKETBASE_URL",
    ""
).strip().rstrip("/")

POCKETBASE_COLLECTION = os.getenv(
    "POCKETBASE_COLLECTION",
    "bookings"
).strip()

POCKETBASE_TOKEN = os.getenv(
    "POCKETBASE_TOKEN",
    ""
).strip()

RESEND_API_KEY = os.getenv(
    "RESEND_API_KEY",
    ""
).strip()

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    
#BASE DIRECTORY

BASE_DIR = Path(__file__).resolve().parent


# =========================================================
# INDIA TIMEZONE
# =========================================================

INDIA_TIME_ZONE = ZoneInfo(
    "Asia/Kolkata"
)


# =========================================================
# SALON TIMING
# =========================================================
#
# Salon:
# 10:00 AM → 08:00 PM
#
# Booking:
# First slot starts at 10:30 AM
# Slots are generated every 15 minutes
#
# Service duration is checked dynamically.
#
# Example:
# 60-minute service at 7:30 PM
# would end at 8:30 PM → NOT ALLOWED.
#
# =========================================================

OPEN_HOUR = 10
CLOSE_HOUR = 20

SHOP_OPEN_TIME = "10:00"
SHOP_CLOSE_TIME = "20:00"

FIRST_BOOKING_TIME = "10:30"

# Latest selectable starting time.
# Final service-duration validation is handled
# by validate_booking_time() later.
LAST_BOOKING_TIME = "19:30"

SLOT_INTERVAL_MINUTES = 15


# =========================================================
# BOOKING DATE RANGE
# =========================================================
#
# Customer can book:
# TODAY + NEXT 7 DAYS
#
# =========================================================

MAX_BOOKING_DAYS = 7


# =========================================================
# POCKETBASE DATABASE
# =========================================================
#
# PocketBase is hosted on PocketHost.io.
#
# Example:
#
# https://your-project.pockethost.io
#
# IMPORTANT:
# Keep POCKETBASE_URL in Render Environment Variables.
#
# =========================================================

POCKETBASE_URL = os.getenv(
    "POCKETBASE_URL",
    ""
).strip().rstrip("/")


# =========================================================
# POCKETBASE COLLECTION
# =========================================================

POCKETBASE_COLLECTION = os.getenv(
    "POCKETBASE_COLLECTION",
    "bookings"
).strip()


# =========================================================
# OPTIONAL POCKETBASE TOKEN
# =========================================================
#
# If your PocketBase collection requires authentication,
# put the token in Render Environment Variables.
#
# Never hard-code a private token in app.py.
#
# =========================================================

POCKETBASE_TOKEN = os.getenv(
    "POCKETBASE_TOKEN",
    ""
).strip()


# =========================================================
# OWNER EMAIL
# =========================================================
#
# Used for salon/admin email notifications if required.
#
# =========================================================

OWNER_EMAIL = os.getenv(
    "OWNER_EMAIL",
    "velorastudio@gmail.com"
).strip()


# =========================================================
# APPOINTMENT DATE / TIME VALIDATION
# =========================================================

def validate_appointment_window(
    appointment_date,
    appointment_time
):

    try:

        selected_date = datetime.strptime(
            appointment_date,
            "%Y-%m-%d"
        ).date()

        selected_time = datetime.strptime(
            appointment_time,
            "%H:%M"
        ).time()

    except ValueError:

        return (
            "Please choose a valid "
            "appointment date and time."
        )


    # -----------------------------------------------------
    # Current India time
    # -----------------------------------------------------

    now = datetime.now(
        INDIA_TIME_ZONE
    )

    today = now.date()

    last_date = (
        today
        + timedelta(
            days=MAX_BOOKING_DAYS
        )
    )


    # =====================================================
    # DATE RANGE
    # =====================================================

    if not (
        today
        <= selected_date
        <= last_date
    ):

        return (

            "Appointments can be booked only "
            "for today through the next "

            f"{MAX_BOOKING_DAYS} days."

        )


    # =====================================================
    # BASIC TIME RANGE
    # =====================================================

    first_time = datetime.strptime(
        FIRST_BOOKING_TIME,
        "%H:%M"
    ).time()

    last_time = datetime.strptime(
        LAST_BOOKING_TIME,
        "%H:%M"
    ).time()


    if not (
        first_time
        <= selected_time
        <= last_time
    ):

        return (

            "Appointments are available from "
            "10:30 AM to 7:30 PM."

        )


    # =====================================================
    # 15-MINUTE SLOT VALIDATION
    # =====================================================
    #
    # Valid:
    # 10:30
    # 10:45
    # 11:00
    # 11:15
    # etc.
    #
    # Invalid:
    # 10:35
    # 10:50
    # 11:05
    #
    # =====================================================

    first_slot_minutes = (
        int(FIRST_BOOKING_TIME[:2]) * 60
        +
        int(FIRST_BOOKING_TIME[3:])
    )

    selected_minutes = (
        selected_time.hour * 60
        +
        selected_time.minute
    )


    if (
        selected_minutes
        - first_slot_minutes
    ) % SLOT_INTERVAL_MINUTES != 0:

        return (
            "Please choose a valid "
            "15-minute time slot."
        )


    # =====================================================
    # PAST TIME PROTECTION
    # =====================================================
    #
    # Only applies when customer books TODAY.
    #
    # Future dates can use normal available slots.
    #
    # =====================================================

    if selected_date == today:

        current_time = now.time()

        if selected_time <= current_time:

            return (

                "That time has already passed. "
                "Please choose a later time."

            )


    return None


# =========================================================
# SALON STATUS
# =========================================================

def get_salon_status():

    india_now = datetime.now(
        INDIA_TIME_ZONE
    )

    current_time = india_now.time()


    # -----------------------------------------------------
    # Convert salon timings to time objects
    # -----------------------------------------------------

    opening_time = datetime.strptime(
        SHOP_OPEN_TIME,
        "%H:%M"
    ).time()

    closing_time = datetime.strptime(
        SHOP_CLOSE_TIME,
        "%H:%M"
    ).time()


    # -----------------------------------------------------
    # Open / Closed
    # -----------------------------------------------------

    if (
        opening_time
        <= current_time
        < closing_time
    ):

        return {

            "open": True,

            "text": "OPEN NOW",

            "description":
                "We're open until 8:00 PM IST"

        }


    return {

        "open": False,

        "text": "CLOSED",

        "description":
            "Open daily from 10:00 AM IST"

    }

# =========================================================
# SERVICES
# =========================================================

MEN_SERVICES = [
    {
        "name": "Classic Haircut",
        "description": "Precision cut with styling",
        "price": 299,
        "duration": 30,
        "icon": "✂️"
    },
    {
        "name": "Premium Haircut",
        "description": "Cut, wash, massage & styling",
        "price": 499,
        "duration": 45,
        "icon": "💇"
    },
    {
        "name": "Beard Styling",
        "description": "Shape, trim & finishing",
        "price": 199,
        "duration": 20,
        "icon": "🧔"
    },
    {
        "name": "Hair + Beard Combo",
        "description": "Complete grooming experience",
        "price": 599,
        "duration": 50,
        "icon": "✨"
    },
    {
        "name": "Hair Spa",
        "description": "Deep nourishment & relaxation",
        "price": 799,
        "duration": 45,
        "icon": "🧖"
    },
    {
        "name": "Hair Coloring",
        "description": "Professional color treatment",
        "price": 999,
        "duration": 40,
        "icon": "🎨"
    }
]

WOMEN_SERVICES = [
    {
        "name": "Women's Haircut",
        "description": "Modern cut with professional styling",
        "price": 599,
        "duration": 45,
        "icon": "✂️"
    },
    {
        "name": "Women's Hair Spa",
        "description": "Relaxing nourishment treatment",
        "price": 899,
        "duration": 60,
        "icon": "🧖"
    },
    {
        "name": "Global Hair Color",
        "description": "Premium full hair coloring",
        "price": 1999,
        "duration": 90,
        "icon": "🎨"
    },
    {
        "name": "Highlights",
        "description": "Beautiful customized highlights",
        "price": 1499,
        "duration": 90,
        "icon": "✨"
    },
    {
        "name": "Keratin Treatment",
        "description": "Smooth and glossy finish",
        "price": 2499,
        "duration": 120,
        "icon": "💎"
    },
    {
        "name": "Bridal Styling",
        "description": "Elegant event & bridal styling",
        "price": 2999,
        "duration": 90,
        "icon": "👰"
    }
]

# Combine all services
ALL_SERVICES = MEN_SERVICES + WOMEN_SERVICES

# Service name → price mapping
SERVICE_PRICES = {
    service["name"]: service["price"]
    for service in ALL_SERVICES
}

# Service name → duration mapping
SERVICE_DURATIONS = {
    service["name"]: service["duration"]
    for service in ALL_SERVICES
}

# =========================================================
# COMPLETE SINGLE PAGE HTML
# =========================================================

INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="en" class="scroll-smooth">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Velora Unisex Hair Studio</title>

    <script src="https://cdn.tailwindcss.com"></script>

    <script>
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    fontFamily: {
                        sans: ["Inter", "sans-serif"],
                        serif: ["Playfair Display", "serif"]
                    }
                }
            }
        }
    </script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

    <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@500;600;700&display=swap"
        rel="stylesheet"
    >

    <style>
        html {
            scroll-behavior: smooth;
        }

        body {
            font-family: "Inter", sans-serif;
        }

        .serif {
            font-family: "Playfair Display", serif;
        }

        .time-slots {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }

        .time-slots.open {
            max-height: 420px;
        }

        .time-slot {
            transition: all 0.2s ease;
        }

        .time-slot:hover {
            transform: translateY(-1px);
        }

        .service-card {
            transition:
                transform 0.3s ease,
                box-shadow 0.3s ease,
                border-color 0.3s ease;
        }

        .service-card:hover {
            transform: translateY(-4px);
        }

        .hero-image {
            transition: transform 0.7s ease;
        }

        .hero-image:hover {
            transform: scale(1.02);
        }
    </style>
</head>


<body
    class="bg-[#F8F5EF] text-[#242424]
           dark:bg-[#111111] dark:text-white
           transition-colors duration-300"
>


<!-- =========================================================
     NAVBAR
     ========================================================= -->

<header
    class="sticky top-0 z-50
           bg-[#F8F5EF]/95 dark:bg-[#111111]/95
           backdrop-blur-xl
           border-b border-black/10 dark:border-white/10"
>

    <div class="max-w-7xl mx-auto px-5 lg:px-8">

        <div class="h-20 flex items-center justify-between">

            <a href="#home" class="flex items-center gap-3">

                <div
                    class="w-11 h-11 rounded-full
                           bg-[#C9A227] text-white
                           flex items-center justify-center
                           font-bold text-lg"
                >
                    V
                </div>

                <div>
                    <div class="serif text-xl font-semibold">
                        Velora
                    </div>

                    <div class="text-[10px] tracking-[0.25em] uppercase opacity-60">
                        Unisex Hair Studio
                    </div>
                </div>

            </a>


            <nav class="hidden md:flex items-center gap-8 text-sm font-medium">

                <a href="#home" class="hover:text-[#C9A227] transition">
                    Home
                </a>

                <a href="#services" class="hover:text-[#C9A227] transition">
                    Services
                </a>

                <a href="#about" class="hover:text-[#C9A227] transition">
                    About
                </a>

                <a href="#booking" class="hover:text-[#C9A227] transition">
                    Booking
                </a>

            </nav>


            <div class="flex items-center gap-3">

                <button
                    id="themeToggle"
                    type="button"
                    class="w-10 h-10 rounded-full
                           border border-black/10 dark:border-white/10
                           flex items-center justify-center
                           hover:border-[#C9A227]
                           transition"
                    aria-label="Toggle theme"
                >
                    ☾
                </button>


                <a
                    href="#booking"
                    class="hidden sm:inline-flex
                           px-5 py-3 rounded-full
                           bg-[#242424] text-white
                           dark:bg-white dark:text-[#242424]
                           text-sm font-semibold
                           hover:bg-[#C9A227]
                           dark:hover:bg-[#C9A227]
                           dark:hover:text-white
                           transition"
                >
                    Book Appointment
                </a>

            </div>

        </div>

    </div>

</header>



<!-- =========================================================
     FLASH MESSAGES
     ========================================================= -->

{% with messages = get_flashed_messages(with_categories=true) %}

{% if messages %}

<div class="max-w-7xl mx-auto px-5 lg:px-8 pt-5">

    {% for category, message in messages %}

    <div
        class="mb-3 rounded-xl px-4 py-3 text-sm font-medium
        {% if category == 'success' %}
            bg-green-100 text-green-800
            dark:bg-green-900/30 dark:text-green-200
        {% else %}
            bg-red-100 text-red-800
            dark:bg-red-900/30 dark:text-red-200
        {% endif %}"
    >
        {{ message }}
    </div>

    {% endfor %}

</div>

{% endif %}

{% endwith %}



<!-- =========================================================
     HERO
     ========================================================= -->

<section id="home" class="relative overflow-hidden">

    <div class="max-w-7xl mx-auto px-5 lg:px-8 py-16 lg:py-24">

        <div class="grid lg:grid-cols-2 gap-12 items-center">

            <div>

                <div
                    class="inline-flex items-center gap-2
                           px-4 py-2 rounded-full
                           border border-[#C9A227]/30
                           bg-[#C9A227]/10
                           text-[#8f7110]
                           dark:text-[#E3C85A]
                           text-xs font-semibold
                           uppercase tracking-wider"
                >
                    <span class="w-2 h-2 rounded-full bg-green-500"></span>

                    {% if salon_open %}
                        Open Now
                    {% else %}
                        Currently Closed
                    {% endif %}
                </div>


                <h1
                    class="serif text-5xl md:text-6xl lg:text-7xl
                           leading-tight mt-6"
                >
                    Your Style.
                    <br>
                    <span class="text-[#C9A227]">
                        Your Identity.
                    </span>
                </h1>


                <p class="mt-6 text-base md:text-lg opacity-65 max-w-xl leading-8">
                    Premium grooming and beauty services designed
                    around your personal style, comfort and confidence.
                </p>


                <div class="flex flex-wrap gap-4 mt-8">

                    <a
                        href="#booking"
                        class="px-6 py-3.5 rounded-full
                               bg-[#242424] text-white
                               dark:bg-white dark:text-[#242424]
                               font-semibold
                               hover:bg-[#C9A227]
                               dark:hover:bg-[#C9A227]
                               dark:hover:text-white
                               transition"
                    >
                        Book Appointment →
                    </a>


                    <a
                        href="#services"
                        class="px-6 py-3.5 rounded-full
                               border border-black/10
                               dark:border-white/10
                               font-semibold
                               hover:border-[#C9A227]
                               transition"
                    >
                        Explore Services
                    </a>

                </div>

            </div>


            <div class="relative">

                <div
                    class="absolute -inset-5
                           bg-[#C9A227]/10
                           blur-3xl rounded-full"
                ></div>

                <img
                    class="hero-image relative w-full
                           h-[520px] object-cover
                           rounded-[2rem]
                           shadow-2xl"
                    src="https://images.unsplash.com/photo-1521590832167-7bcbfaa6381f?auto=format&fit=crop&w=1200&q=85"
                    alt="Velora Hair Studio"
                >

            </div>

        </div>

    </div>

</section>



<!-- =========================================================
     SERVICES
     ========================================================= -->

<section id="services" class="py-20">

    <div class="max-w-7xl mx-auto px-5 lg:px-8">

        <div class="max-w-2xl mb-12">

            <p
                class="text-[#C9A227] text-sm
                       uppercase tracking-[0.2em]
                       font-semibold"
            >
                Our Services
            </p>

            <h2 class="serif text-4xl md:text-5xl mt-3">
                Crafted for Your Style
            </h2>

            <p class="mt-4 opacity-60 leading-7">
                Professional grooming and beauty services
                with transparent pricing and service duration.
            </p>

        </div>


        <!-- MEN -->

        <div class="mb-14">

            <div class="flex items-center gap-4 mb-6">

                <h3 class="serif text-2xl">
                    Men
                </h3>

                <div class="h-px flex-1 bg-black/10 dark:bg-white/10"></div>

            </div>


            <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">

                {% for service in men_services %}

                <div
                    class="service-card
                           rounded-2xl
                           border border-black/10
                           dark:border-white/10
                           bg-white/70 dark:bg-white/[0.04]
                           p-6"
                >

                    <div class="flex justify-between gap-4">

                        <div>

                            <div
                                class="w-12 h-12 rounded-xl
                                       bg-[#C9A227]/10
                                       flex items-center justify-center
                                       text-2xl mb-5"
                            >
                                {{ service.icon }}
                            </div>

                            <h4 class="font-semibold text-lg">
                                {{ service.name }}
                            </h4>

                            <p class="text-sm opacity-55 mt-2 leading-6">
                                {{ service.description }}
                            </p>

                        </div>


                        <!-- PRICE + DURATION -->

                        <div class="text-right shrink-0">

                            <div class="text-xl font-bold text-[#C9A227]">
                                ₹{{ service.price }}
                            </div>

                            <div class="text-xs opacity-50 mt-1">
                                {{ service.duration }} min
                            </div>

                        </div>

                    </div>


                    <button
                        type="button"
                        onclick="selectService('{{ service.name|replace("'", "\\'") }}')"
                        class="mt-6 text-sm font-semibold
                               hover:text-[#C9A227]
                               transition"
                    >
                        Book this service →
                    </button>

                </div>

                {% endfor %}

            </div>

        </div>



        <!-- WOMEN -->

        <div>

            <div class="flex items-center gap-4 mb-6">

                <h3 class="serif text-2xl">
                    Women
                </h3>

                <div class="h-px flex-1 bg-black/10 dark:bg-white/10"></div>

            </div>


            <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">

                {% for service in women_services %}

                <div
                    class="service-card
                           rounded-2xl
                           border border-black/10
                           dark:border-white/10
                           bg-white/70 dark:bg-white/[0.04]
                           p-6"
                >

                    <div class="flex justify-between gap-4">

                        <div>

                            <div
                                class="w-12 h-12 rounded-xl
                                       bg-[#C9A227]/10
                                       flex items-center justify-center
                                       text-2xl mb-5"
                            >
                                {{ service.icon }}
                            </div>

                            <h4 class="font-semibold text-lg">
                                {{ service.name }}
                            </h4>

                            <p class="text-sm opacity-55 mt-2 leading-6">
                                {{ service.description }}
                            </p>

                        </div>


                        <!-- PRICE + DURATION -->

                        <div class="text-right shrink-0">

                            <div class="text-xl font-bold text-[#C9A227]">
                                ₹{{ service.price }}
                            </div>

                            <div class="text-xs opacity-50 mt-1">
                                {{ service.duration }} min
                            </div>

                        </div>

                    </div>


                    <button
                        type="button"
                        onclick="selectService('{{ service.name|replace("'", "\\'") }}')"
                        class="mt-6 text-sm font-semibold
                               hover:text-[#C9A227]
                               transition"
                    >
                        Book this service →
                    </button>

                </div>

                {% endfor %}

            </div>

        </div>

    </div>

</section>



<!-- =========================================================
     ABOUT
     ========================================================= -->

<section id="about" class="py-20 border-y border-black/5 dark:border-white/5">

    <div class="max-w-7xl mx-auto px-5 lg:px-8">

        <div class="grid lg:grid-cols-2 gap-12 items-center">

            <img
                src="https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=1200&q=85"
                alt="Professional salon"
                class="w-full h-[460px] object-cover rounded-[2rem]"
            >


            <div>

                <p
                    class="text-[#C9A227] text-sm
                           uppercase tracking-[0.2em]
                           font-semibold"
                >
                    About Velora
                </p>

                <h2 class="serif text-4xl md:text-5xl mt-3">
                    More Than a Haircut
                </h2>

                <p class="mt-6 opacity-65 leading-8">
                    At Velora Unisex Hair Studio, we combine
                    professional techniques, premium products
                    and a comfortable environment to create
                    a grooming experience that feels personal.
                </p>


                <div class="grid grid-cols-2 gap-5 mt-8">

                    <div
                        class="p-5 rounded-2xl
                               border border-black/10
                               dark:border-white/10"
                    >
                        <div class="text-2xl font-bold text-[#C9A227]">
                            10 AM
                        </div>

                        <div class="text-sm opacity-55 mt-1">
                            Opening Time
                        </div>
                    </div>


                    <div
                        class="p-5 rounded-2xl
                               border border-black/10
                               dark:border-white/10"
                    >
                        <div class="text-2xl font-bold text-[#C9A227]">
                            9 PM
                        </div>

                        <div class="text-sm opacity-55 mt-1">
                            Closing Time
                        </div>
                    </div>

                </div>

            </div>

        </div>

    </div>

</section>



<!-- =========================================================
     BOOKING
     ========================================================= -->

<section id="booking" class="py-20">

    <div class="max-w-4xl mx-auto px-5 lg:px-8">

        <div class="text-center mb-10">

            <p
                class="text-[#C9A227] text-sm
                       uppercase tracking-[0.2em]
                       font-semibold"
            >
                Appointment
            </p>

            <h2 class="serif text-4xl md:text-5xl mt-3">
                Book Your Visit
            </h2>

            <p class="mt-4 opacity-60">
                Select your service, stylist and preferred time.
            </p>

        </div>


        <form
            id="bookingForm"
            action="{{ url_for('book') }}"
            method="POST"
            class="rounded-[2rem]
                   bg-white dark:bg-white/[0.04]
                   border border-black/10
                   dark:border-white/10
                   p-6 md:p-8 shadow-xl"
        >

            <div class="grid md:grid-cols-2 gap-5">


                <!-- NAME -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Full Name
                    </label>

                    <input
                        type="text"
                        name="name"
                        required
                        autocomplete="name"
                        placeholder="Enter your name"
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               focus:border-[#C9A227]
                               transition"
                    >

                </div>


                <!-- PHONE -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Phone Number
                    </label>

                    <input
                        type="tel"
                        name="phone"
                        required
                        autocomplete="tel"
                        placeholder="Enter phone number"
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               focus:border-[#C9A227]
                               transition"
                    >

                </div>


                <!-- EMAIL -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Email
                    </label>

                    <input
                        type="email"
                        name="email"
                        autocomplete="email"
                        placeholder="Enter email address"
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               focus:border-[#C9A227]
                               transition"
                    >

                </div>


                <!-- AUDIENCE -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Category
                    </label>

                    <select
                        id="audienceSelect"
                        name="audience"
                        required
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               focus:border-[#C9A227]
                               transition"
                    >

                        <option value="">
                            Select category
                        </option>

                        <option value="men">
                            Men
                        </option>

                        <option value="women">
                            Women
                        </option>

                    </select>

                </div>


                <!-- SERVICE -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Service
                    </label>

                    <select
                        id="serviceSelect"
                        name="service"
                        required
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               focus:border-[#C9A227]
                               transition"
                    >

                        <option value="">
                            Choose a service
                        </option>


                        {% for service in men_services %}

                        <option
                            value="{{ service.name }}"
                            data-price="{{ service.price }}"
                            data-duration="{{ service.duration }}"
                            data-category="men"
                        >
                            {{ service.name }}
                            — ₹{{ service.price }}
                            · {{ service.duration }} min
                        </option>

                        {% endfor %}


                        {% for service in women_services %}

                        <option
                            value="{{ service.name }}"
                            data-price="{{ service.price }}"
                            data-duration="{{ service.duration }}"
                            data-category="women"
                        >
                            {{ service.name }}
                            — ₹{{ service.price }}
                            · {{ service.duration }} min
                        </option>

                        {% endfor %}

                    </select>

                </div>


                <!-- STYLIST -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Stylist
                    </label>

                    <select
                        name="stylist"
                        required
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               focus:border-[#C9A227]
                               transition"
                    >

                        <option value="">
                            Choose stylist
                        </option>

                        {% for stylist in stylists %}

                        <option value="{{ stylist.name }}">
                            {{ stylist.name }}
                        </option>

                        {% endfor %}

                    </select>

                </div>


                <!-- DATE -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Appointment Date
                    </label>

                    <input
                        id="appointmentDate"
                        type="date"
                        name="date"
                        required
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               focus:border-[#C9A227]
                               transition"
                    >

                </div>


                <!-- TIME -->

                <div>

                    <label class="block text-sm font-semibold mb-2">
                        Appointment Time
                    </label>

                    <button
                        id="timePickerToggle"
                        type="button"
                        class="w-full px-4 py-3.5 rounded-xl
                               bg-[#F8F5EF] dark:bg-[#151515]
                               border border-black/10
                               dark:border-white/10
                               outline-none
                               text-left
                               focus:border-[#C9A227]
                               transition"
                    >
                        Choose a time
                    </button>


                    <input
                        id="appointmentTime"
                        type="hidden"
                        name="time"
                        required
                    >


                    <div
                        id="timeSlots"
                        class="time-slots mt-3
                               grid grid-cols-3 sm:grid-cols-4
                               gap-2"
                    >
                    </div>

                </div>

            </div>


            <!-- AVAILABILITY -->

            <div
                id="availabilityMessage"
                class="hidden mt-5 rounded-xl
                       px-4 py-3 text-sm font-semibold"
            >
            </div>


            <!-- SUBMIT -->

            <button
                type="submit"
                class="w-full mt-6
                       px-6 py-4 rounded-xl
                       bg-[#242424] text-white
                       dark:bg-white dark:text-[#242424]
                       font-semibold
                       hover:bg-[#C9A227]
                       dark:hover:bg-[#C9A227]
                       dark:hover:text-white
                       transition"
            >
                Confirm Appointment →
            </button>

        </form>

    </div>

</section>



<!-- =========================================================
     FOOTER
     ========================================================= -->

<footer class="border-t border-black/10 dark:border-white/10">

    <div class="max-w-7xl mx-auto px-5 lg:px-8 py-10">

        <div class="grid md:grid-cols-3 gap-8">

            <div>

                <div class="serif text-2xl font-semibold">
                    Velora
                </div>

                <p class="text-sm opacity-55 mt-2">
                    Unisex Hair Studio
                </p>

            </div>


            <div>

                <h4 class="font-semibold mb-3">
                    Opening Hours
                </h4>

                <p class="text-sm opacity-60">
                    Every Day
                </p>

                <p class="text-sm opacity-60 mt-1">
                    10:00 AM — 9:00 PM
                </p>

            </div>


            <div>

                <h4 class="font-semibold mb-3">
                    Quick Links
                </h4>

                <div class="flex flex-col gap-2 text-sm opacity-60">

                    <a href="#services" class="hover:text-[#C9A227]">
                        Services
                    </a>

                    <a href="#about" class="hover:text-[#C9A227]">
                        About
                    </a>

                    <a href="#booking" class="hover:text-[#C9A227]">
                        Booking
                    </a>

                </div>

            </div>

        </div>

    </div>

</footer>



<!-- =========================================================
     JAVASCRIPT
     ========================================================= -->

<script>

document.addEventListener("DOMContentLoaded", () => {

    const themeToggle = document.getElementById("themeToggle");

    const serviceSelect =
        document.getElementById("serviceSelect");

    const audienceSelect =
        document.getElementById("audienceSelect");

    const stylistInput =
        document.querySelector('select[name="stylist"]');

    const dateInput =
        document.getElementById("appointmentDate");

    const timeInput =
        document.getElementById("appointmentTime");

    const timePickerToggle =
        document.getElementById("timePickerToggle");

    const timeSlots =
        document.getElementById("timeSlots");

    const availabilityMessage =
        document.getElementById("availabilityMessage");

    let availabilityRequest = null;


    /* =====================================================
       THEME
       ===================================================== */

    const savedTheme =
        localStorage.getItem("velora-theme");

    if (savedTheme === "dark") {
        document.documentElement.classList.add("dark");
        themeToggle.textContent = "☀";
    }


    themeToggle.addEventListener("click", () => {

        document.documentElement.classList.toggle("dark");

        const isDark =
            document.documentElement.classList.contains("dark");

        localStorage.setItem(
            "velora-theme",
            isDark ? "dark" : "light"
        );

        themeToggle.textContent =
            isDark ? "☀" : "☾";

    });


    /* =====================================================
       MINIMUM DATE
       ===================================================== */

    const today = new Date();

    const localToday =
        new Date(
            today.getTime()
            - today.getTimezoneOffset() * 60000
        )
        .toISOString()
        .split("T")[0];

    dateInput.min = localToday;


    /* =====================================================
       TIME SLOTS
       ===================================================== */

    for (
        let minutes = 600;
        minutes <= 1230;
        minutes += 15
    ) {

        const hours =
            Math.floor(minutes / 60);

        const mins =
            minutes % 60;

        const displayHour =
            hours > 12
                ? hours - 12
                : hours;

        const period =
            hours >= 12 ? "PM" : "AM";

        const label =
            `${displayHour}:${String(mins).padStart(2, "0")} ${period}`;

        const value =
            `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;

        const button =
            document.createElement("button");

        button.type = "button";

        button.className =
            "time-slot px-3 py-2.5 rounded-lg " +
            "border border-black/10 dark:border-white/10 " +
            "text-sm font-medium " +
            "hover:border-[#C9A227] " +
            "transition";

        button.textContent = label;

        button.dataset.value = value;


        button.addEventListener("click", () => {

            timeInput.value = value;

            timePickerToggle.textContent = label;

            timeSlots
                .querySelectorAll(".time-slot")
                .forEach(item => {
                    item.classList.remove(
                        "selected",
                        "bg-[#C9A227]",
                        "text-white"
                    );
                });

            button.classList.add(
                "selected",
                "bg-[#C9A227]",
                "text-white"
            );

            timeSlots.classList.remove("open");

            checkAvailability();

        });


        timeSlots.appendChild(button);

    }


    timePickerToggle.addEventListener("click", () => {

        timeSlots.classList.toggle("open");

    });


    /* =====================================================
       SERVICE → CATEGORY SYNC
       ===================================================== */

    serviceSelect.addEventListener("change", () => {

        const selectedOption =
            serviceSelect.options[
                serviceSelect.selectedIndex
            ];

        if (!selectedOption) {
            return;
        }

        const category =
            selectedOption.dataset.category;

        if (category) {
            audienceSelect.value = category;
        }

        checkAvailability();

    });


    /* =====================================================
       AVAILABILITY CHECK
       ===================================================== */

    async function checkAvailability() {

        const date =
            dateInput.value;

        const time =
            timeInput.value;

        const stylist =
            stylistInput.value;

        const service =
            serviceSelect.value;


        if (
            !date ||
            !time ||
            !stylist ||
            !service
        ) {

            availabilityMessage.classList.add(
                "hidden"
            );

            return;
        }


        if (availabilityRequest) {
            availabilityRequest.abort();
        }


        availabilityRequest =
            new AbortController();


        availabilityMessage.textContent =
            "Checking availability...";

        availabilityMessage.className =
            "mt-4 rounded-xl px-4 py-3 text-sm font-semibold " +
            "bg-black/5 text-black/70 " +
            "dark:bg-white/10 dark:text-white/70";

        availabilityMessage.classList.remove(
            "hidden"
        );


        try {

            const response =
                await fetch(
                    `/availability?date=${encodeURIComponent(date)}` +
                    `&time=${encodeURIComponent(time)}` +
                    `&stylist=${encodeURIComponent(stylist)}` +
                    `&service=${encodeURIComponent(service)}`,
                    {
                        signal:
                            availabilityRequest.signal
                    }
                );


            const result =
                await response.json();


            availabilityMessage.textContent =
                result.message ||
                (
                    result.available
                        ? "This time is available."
                        : "This time is not available."
                );


            if (result.available) {

                availabilityMessage.className =
                    "mt-4 rounded-xl px-4 py-3 text-sm font-semibold " +
                    "bg-green-100 text-green-800 " +
                    "dark:bg-green-900/30 dark:text-green-200";

            } else {

                availabilityMessage.className =
                    "mt-4 rounded-xl px-4 py-3 text-sm font-semibold " +
                    "bg-red-100 text-red-800 " +
                    "dark:bg-red-900/30 dark:text-red-200";

            }


            availabilityMessage.classList.remove(
                "hidden"
            );

        }

        catch (error) {

            if (error.name === "AbortError") {
                return;
            }


            availabilityMessage.textContent =
                "Availability could not be checked. Please try again.";


            availabilityMessage.className =
                "mt-4 rounded-xl px-4 py-3 text-sm font-semibold " +
                "bg-red-100 text-red-800 " +
                "dark:bg-red-900/30 dark:text-red-200";


            availabilityMessage.classList.remove(
                "hidden"
            );

        }

    }


    /* =====================================================
       AVAILABILITY EVENTS
       ===================================================== */

    [
        dateInput,
        timeInput,
        stylistInput,
        serviceSelect
    ].forEach(input => {

        input.addEventListener(
            "change",
            checkAvailability
        );

    });


    /* =====================================================
       BOOKING SUBMIT
       ===================================================== */

    document
        .getElementById("bookingForm")
        .addEventListener("submit", async event => {

            event.preventDefault();


            const form =
                event.currentTarget;

            const submitButton =
                form.querySelector(
                    'button[type="submit"]'
                );


            submitButton.disabled = true;

            submitButton.textContent =
                "Confirming...";


            try {

                const response =
                    await fetch(
                        form.action,
                        {
                            method: "POST",
                            body:
                                new FormData(form),
                            headers: {
                                "Accept":
                                    "application/json"
                            }
                        }
                    );


                const result =
                    await response.json();


                availabilityMessage.textContent =
                    result.message ||
                    "Unable to complete booking.";


                availabilityMessage.className =
                    result.ok

                        ? "mt-4 rounded-xl px-4 py-3 text-sm font-semibold " +
                          "bg-green-100 text-green-800 " +
                          "dark:bg-green-900/30 dark:text-green-200"

                        : "mt-4 rounded-xl px-4 py-3 text-sm font-semibold " +
                          "bg-red-100 text-red-800 " +
                          "dark:bg-red-900/30 dark:text-red-200";


                availabilityMessage.classList.remove(
                    "hidden"
                );


                if (result.ok) {

                    form.reset();

                    timeInput.value = "";

                    timePickerToggle.textContent =
                        "Choose a time";

                    timeSlots.classList.remove(
                        "open"
                    );

                    timeSlots
                        .querySelectorAll(".time-slot")
                        .forEach(item => {

                            item.classList.remove(
                                "selected",
                                "bg-[#C9A227]",
                                "text-white"
                            );

                        });

                }

            }

            catch (error) {

                availabilityMessage.textContent =
                    "Booking could not be completed. Please try again.";


                availabilityMessage.className =
                    "mt-4 rounded-xl px-4 py-3 text-sm font-semibold " +
                    "bg-red-100 text-red-800 " +
                    "dark:bg-red-900/30 dark:text-red-200";


                availabilityMessage.classList.remove(
                    "hidden"
                );

            }

            finally {

                submitButton.disabled = false;

                submitButton.textContent =
                    "Confirm Appointment →";

            }

        });

});



/* =========================================================
   SERVICE CARD → BOOKING
   ========================================================= */

function selectService(serviceName) {

    const serviceSelect =
        document.getElementById(
            "serviceSelect"
        );

    const audienceSelect =
        document.getElementById(
            "audienceSelect"
        );


    serviceSelect.value =
        serviceName;


    const selectedOption =
        serviceSelect.options[
            serviceSelect.selectedIndex
        ];


    if (selectedOption) {

        const category =
            selectedOption.dataset.category;

        if (category) {
            audienceSelect.value =
                category;
        }

    }


    document
        .getElementById("booking")
        .scrollIntoView({
            behavior: "smooth"
        });


    serviceSelect.dispatchEvent(
        new Event("change")
    );

}

</script>

</body>
</html>
"""



# =========================================================
# ADMIN HTML
# =========================================================

ADMIN_HTML = r"""
<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Velora Admin</title>

    <script src="https://cdn.tailwindcss.com"></script>

    <script>
        tailwind.config = {
            darkMode: "class"
        }
    </script>

</head>


<body
    class="bg-[#F8F5EF] text-[#242424]
           dark:bg-[#111111] dark:text-white"
>


<div class="max-w-7xl mx-auto px-5 py-10">


    <!-- HEADER -->

    <div
        class="flex flex-col md:flex-row
               md:items-center
               md:justify-between
               gap-5 mb-8"
    >

        <div>

            <p
                class="text-xs uppercase
                       tracking-[0.2em]
                       text-[#C9A227]
                       font-semibold"
            >
                Velora
            </p>

            <h1 class="text-3xl font-bold mt-1">
                Appointment Dashboard
            </h1>

            <p class="text-sm opacity-55 mt-2">
                Manage salon appointments
            </p>

        </div>


        <div class="flex items-center gap-3">

            <div
                class="px-4 py-2 rounded-full
                       bg-green-100 text-green-800
                       dark:bg-green-900/30
                       dark:text-green-200
                       text-sm font-semibold"
            >
                ● Database Connected
            </div>


            <a
                href="{{ url_for('home') }}"
                class="px-5 py-2.5 rounded-xl
                       bg-[#242424] text-white
                       dark:bg-white dark:text-[#242424]
                       text-sm font-semibold"
            >
                View Website
            </a>

        </div>

    </div>



    <!-- APPOINTMENTS -->

    <div
        class="rounded-2xl overflow-hidden
               border border-black/10
               dark:border-white/10
               bg-white dark:bg-white/[0.04]"
    >

        <div class="overflow-x-auto">

            <table class="w-full text-left">

                <thead
                    class="bg-black/[0.03]
                           dark:bg-white/[0.04]"
                >

                    <tr>

                        <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">
                            ID
                        </th>

                        <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">
                            Customer
                        </th>

                        <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">
                            Phone
                        </th>

                        <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">
                            Service
                        </th>

                        <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">
                            Stylist
                        </th>

                        <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">
                            Date
                        </th>

                        <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">
                            Time
                        </th>

                    </tr>

                </thead>


                <tbody>

                    {% for appointment in appointments %}

                    <tr
                        class="border-t border-black/5
                               dark:border-white/5
                               hover:bg-black/[0.02]
                               dark:hover:bg-white/[0.02]"
                    >

                        <td class="px-5 py-4 text-sm">
                            {{ appointment.id }}
                        </td>

                        <td class="px-5 py-4">

                            <div class="font-semibold">
                                {{ appointment.name }}
                            </div>

                            {% if appointment.email %}
                            <div class="text-xs opacity-50 mt-1">
                                {{ appointment.email }}
                            </div>
                            {% endif %}

                        </td>

                        <td class="px-5 py-4 text-sm">
                            {{ appointment.phone }}
                        </td>

                        <td class="px-5 py-4">

                            <div class="font-medium">
                                {{ appointment.service }}
                            </div>

                            {% if appointment.duration %}
                            <div class="text-xs opacity-50 mt-1">
                                {{ appointment.duration }} min
                            </div>
                            {% endif %}

                        </td>

                        <td class="px-5 py-4 text-sm">
                            {{ appointment.stylist }}
                        </td>

                        <td class="px-5 py-4 text-sm">
                            {{ appointment.date }}
                        </td>

                        <td class="px-5 py-4 text-sm font-semibold">
                            {{ appointment.time }}
                        </td>

                    </tr>

                    {% else %}

                    <tr>

                        <td
                            colspan="7"
                            class="px-5 py-14
                                   text-center
                                   opacity-50"
                        >
                            No appointments found.
                        </td>

                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

    </div>

</div>

</body>
</html>
"""

# =========================================================
# HOME ROUTE
# =========================================================
@app.route("/")
def home():
    status = get_salon_status()

    return render_template_string(
        INDEX_HTML,

        # Salon status
        status=status,
        salon_open=status["open"],

        # Service data
        men_services=MEN_SERVICES,
        women_services=WOMEN_SERVICES,

        # Stylist data
        stylists=STYLISTS
    )

STYLISTS = [
    {
        "id": "arjun",
        "name": "Arjun",
        "specialty": "Men's Grooming",
        "email": "swaminathji170@gmail.com"
    },
    {
        "id": "karan",
        "name": "Karan",
        "specialty": "Men's Styling",
        "email": "ranvjbundela48@gmail.com"
    },
    {
        "id": "riya",
        "name": "Riya",
        "specialty": "Women's Styling",
        "email": "swaminathji170@gmail.com"
    },
    {
        "id": "meera",
        "name": "Meera",
        "specialty": "Hair & Beauty",
        "email": "ranvjbundela48@gmail.com"
    }
]
# =========================================================
# POCKETBASE HELPER
# =========================================================

def pocketbase_headers():

    headers = {
        "Content-Type": "application/json"
    }

    if POCKETBASE_TOKEN:
        headers["Authorization"] = (
            f"Bearer {POCKETBASE_TOKEN}"
        )

    return headers


# =========================================================
# POCKETBASE BOOKING FETCH
# =========================================================

def get_pocketbase_bookings(
    appointment_date,
    stylist
):
    """
    Get confirmed bookings for the selected
    date and stylist.

    Date/time are stored as plain text:
    booking_date = YYYY-MM-DD
    start_time   = HH:MM
    end_time     = HH:MM
    """

    if not POCKETBASE_URL:
        raise RuntimeError(
            "POCKETBASE_URL is not configured."
        )

    filter_value = (
        f'booking_date="{appointment_date}" '
        f'&& stylist="{stylist}" '
        f'&& status="confirmed"'
    )

    params = {
        "filter": filter_value,
        "perPage": 200,
        "page": 1
    }

    url = (
        f"{POCKETBASE_URL.rstrip('/')}"
        f"/api/collections/"
        f"{POCKETBASE_COLLECTION}"
        f"/records"
    )

    response = requests.get(
        url,
        headers=pocketbase_headers(),
        params=params,
        timeout=15
    )

    print(
        "POCKETBASE AVAILABILITY URL:",
        response.url
    )

    print(
        "POCKETBASE AVAILABILITY STATUS:",
        response.status_code
    )

    print(
        "POCKETBASE AVAILABILITY RESPONSE:",
        response.text
    )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "items",
        []
    )

# =========================================================
# APPOINTMENT TIME HELPERS
# =========================================================

def get_appointment_times(
    appointment_date,
    appointment_time,
    service
):
    """
    Returns appointment start and end datetime.

    Duration comes from SERVICE_DURATIONS.
    """

    duration = SERVICE_DURATIONS.get(
        service
    )

    if duration is None:
        raise ValueError(
            "Invalid service."
        )

    start_datetime = datetime.strptime(
        f"{appointment_date} {appointment_time}",
        "%Y-%m-%d %H:%M"
    )

    end_datetime = (
        start_datetime
        + timedelta(minutes=int(duration))
    )

    return start_datetime, end_datetime

# =========================================================
# TIME CONVERSION
# =========================================================

def time_to_minutes(time_string):
    """
    Convert HH:MM into minutes from midnight.

    Example:
    10:00 -> 600
    10:30 -> 630
    19:30 -> 1170
    """

    hour, minute = map(
        int,
        time_string.strip().split(":")
    )

    return (
        hour * 60
        + minute
    )


def minutes_to_time(total_minutes):
    """
    Convert minutes from midnight into HH:MM.
    """

    hour = total_minutes // 60
    minute = total_minutes % 60

    return f"{hour:02d}:{minute:02d}"


# =========================================================
# BOOKING OVERLAP CHECK
# =========================================================

def has_booking_overlap(
    new_start_time,
    new_end_time,
    existing_bookings
):
    """
    Check whether the new appointment overlaps
    with an existing confirmed booking.

    No datetime timezone conversion is used here.
    Times are compared as simple HH:MM values.
    """

    new_start = time_to_minutes(
        new_start_time
    )

    new_end = time_to_minutes(
        new_end_time
    )

    for booking in existing_bookings:

        existing_start_time = str(
            booking.get(
                "start_time",
                ""
            )
        ).strip()

        existing_end_time = str(
            booking.get(
                "end_time",
                ""
            )
        ).strip()

        # Ignore incomplete old records
        if not (
            existing_start_time
            and existing_end_time
        ):
            continue

        try:

            existing_start = time_to_minutes(
                existing_start_time
            )

            existing_end = time_to_minutes(
                existing_end_time
            )

        except (ValueError, TypeError):

            continue

        # Overlap formula:
        #
        # New Start < Existing End
        # AND
        # New End > Existing Start

        if (
            new_start < existing_end
            and
            new_end > existing_start
        ):
            return True

    return False

# =========================================================
# COMMON BOOKING TIME VALIDATION
# =========================================================

def validate_booking_time(
    appointment_date,
    appointment_time,
    service
):
    """
    Validates:
    - Date/time format
    - First slot = 10:30 AM
    - 15 minute interval
    - Service duration
    - Closing time = 8:00 PM
    - Past time for today's date
    """

    # -----------------------------------------------------
    # Service
    # -----------------------------------------------------

    service_duration = SERVICE_DURATIONS.get(
        service
    )

    if service_duration is None:

        return (
            False,
            "Please select a valid service.",
            None,
            None
        )

    # -----------------------------------------------------
    # Parse appointment
    # -----------------------------------------------------

    try:

        start_datetime = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M"
        )

    except ValueError:

        return (
            False,
            "Invalid appointment date or time.",
            None,
            None
        )

    # -----------------------------------------------------
    # First slot = 10:30 AM
    # -----------------------------------------------------

    first_slot = datetime.strptime(
        FIRST_BOOKING_TIME,
        "%H:%M"
    ).time()

    if start_datetime.time() < first_slot:

        return (
            False,
            "Bookings start from 10:30 AM.",
            None,
            None
        )

    # -----------------------------------------------------
    # 15-minute slot validation
    # -----------------------------------------------------

    first_slot_minutes = (
        int(FIRST_BOOKING_TIME[:2]) * 60
        + int(FIRST_BOOKING_TIME[3:])
    )

    selected_minutes = (
        start_datetime.hour * 60
        + start_datetime.minute
    )

    if (
        selected_minutes - first_slot_minutes
    ) % SLOT_INTERVAL_MINUTES != 0:

        return (
            False,
            "Please select a valid 15-minute time slot.",
            None,
            None
        )

    # -----------------------------------------------------
    # Calculate service end
    # -----------------------------------------------------

    end_datetime = (
        start_datetime
        + timedelta(
            minutes=int(service_duration)
        )
    )

    # -----------------------------------------------------
    # Salon closing = 8:00 PM
    # -----------------------------------------------------

    salon_close = start_datetime.replace(
        hour=20,
        minute=0,
        second=0,
        microsecond=0
    )

    if end_datetime > salon_close:

        return (
            False,
            (
                f"This service takes "
                f"{service_duration} minutes and "
                "must finish by 8:00 PM."
            ),
            None,
            None
        )

    # -----------------------------------------------------
    # Past time filter
    #
    # Only applies when selected date is TODAY.
    # -----------------------------------------------------

    now_india = datetime.now(
        INDIA_TIME_ZONE
    )

    today_string = now_india.strftime(
        "%Y-%m-%d"
    )

    if appointment_date == today_string:

        current_datetime = now_india.replace(
            tzinfo=None
        )

        if start_datetime <= current_datetime:

            return (
                False,
                "This time slot has already passed.",
                None,
                None
            )

    return (
        True,
        "",
        start_datetime,
        end_datetime
    )


@app.route("/test-pocketbase")
def test_pocketbase():
    try:
        # Check configuration
        if not POCKETBASE_URL:
            return jsonify({
                "ok": False,
                "step": "configuration",
                "message": "POCKETBASE_URL is empty."
            }), 500

        # Test PocketBase API
        url = f"{POCKETBASE_URL}/api/collections/{POCKETBASE_COLLECTION}/records"

        response = requests.get(
            url,
            headers=pocketbase_headers(),
            params={
                "page": 1,
                "perPage": 1
            },
            timeout=10
        )

        print("POCKETBASE TEST URL:", url)
        print("POCKETBASE STATUS:", response.status_code)
        print("POCKETBASE RESPONSE:", response.text)

        if response.ok:
            return jsonify({
                "ok": True,
                "message": "PocketBase connection successful.",
                "pocketbase_url": POCKETBASE_URL,
                "collection": POCKETBASE_COLLECTION,
                "status_code": response.status_code
            })

        return jsonify({
            "ok": False,
            "message": "PocketBase responded with an error.",
            "status_code": response.status_code,
            "response": response.text
        }), 500

    except requests.RequestException as error:
        print("POCKETBASE CONNECTION ERROR:", repr(error))

        return jsonify({
            "ok": False,
            "message": "Could not connect to PocketBase.",
            "error": repr(error)
        }), 500

    except Exception as error:
        print("POCKETBASE TEST ERROR:", repr(error))

        return jsonify({
            "ok": False,
            "message": "PocketBase test failed.",
            "error": repr(error)
        }), 500

# =========================================================
# CHECK SLOTS
# =========================================================

@app.route("/check-slots", methods=["GET"])
def check_slots():

    try:
        appointment_date = request.args.get("date", "").strip()
        appointment_time = request.args.get("time", "").strip()
        stylist = request.args.get("stylist", "").strip()
        service = request.args.get("service", "").strip()

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not all([
            appointment_date,
            appointment_time,
            stylist,
            service
        ]):
            return jsonify({
                "ok": False,
                "available": False,
                "message": "Please select date, time, service and stylist."
            }), 400

        # -------------------------------------------------
        # SERVICE VALIDATION
        # -------------------------------------------------

        if service not in SERVICE_DURATIONS:
            return jsonify({
                "ok": False,
                "available": False,
                "message": "Invalid service selected."
            }), 400

        # -------------------------------------------------
        # TIME VALIDATION
        # -------------------------------------------------

        valid, message, start_datetime, end_datetime = (
            validate_booking_time(
                appointment_date,
                appointment_time,
                service
            )
        )

        if not valid:
            return jsonify({
                "ok": True,
                "available": False,
                "message": message
            }), 200

        # -------------------------------------------------
        # POCKETBASE CONFIGURATION
        # -------------------------------------------------

        if not POCKETBASE_URL:
            print("ERROR: POCKETBASE_URL is empty.")

            return jsonify({
                "ok": False,
                "available": False,
                "message": "PocketBase is not configured."
            }), 500

        # -------------------------------------------------
        # GET EXISTING BOOKINGS
        # -------------------------------------------------

        try:
            existing_bookings = get_pocketbase_bookings(
                appointment_date,
                stylist
            )

        except requests.RequestException as error:
            print(
                "POCKETBASE AVAILABILITY ERROR:",
                repr(error)
            )

            return jsonify({
                "ok": False,
                "available": False,
                "message": "Availability could not be checked. Please try again."
            }), 503

        except Exception as error:
            print(
                "AVAILABILITY ERROR:",
                repr(error)
            )

            return jsonify({
                "ok": False,
                "available": False,
                "message": "Availability could not be checked. Please try again."
            }), 503

        # -------------------------------------------------
        # CHECK OVERLAP
        # -------------------------------------------------

        if has_booking_overlap(
            start_datetime,
            end_datetime,
            existing_bookings
        ):
            return jsonify({
                "ok": True,
                "available": False,
                "message": "This time slot is already booked with the selected stylist."
            }), 200

        # -------------------------------------------------
        # AVAILABLE
        # -------------------------------------------------

        return jsonify({
            "ok": True,
            "available": True,
            "message": "This appointment slot is available.",
            "duration_minutes": SERVICE_DURATIONS[service]
        }), 200

    except Exception as error:

        print(
            "CHECK SLOTS ERROR:",
            repr(error)
        )

        return jsonify({
            "ok": False,
            "available": False,
            "message": "Availability could not be checked. Please try again."
        }), 500

    # -----------------------------------------------------
    # DYNAMIC COLLISION CHECK
    # -----------------------------------------------------

    if has_booking_overlap(

        new_start,

        new_end,

        existing_bookings

    ):

        return jsonify({

            "ok": False,

            "available": False,

            "code": "UNAVAILABLE",

            "message": (
                "This time slot is not available "
                "for the selected stylist."
            )

        }), 409

    # -----------------------------------------------------
    # AVAILABLE
    # -----------------------------------------------------

    return jsonify({

        "ok": True,

        "available": True,

        "code": "AVAILABLE",

        "message": (
            "Time slot is available."
        ),

        "duration_minutes": service_duration

    }), 200

# =========================================================
# CUSTOMER CONFIRMATION EMAIL - RESEND
# =========================================================

def send_customer_confirmation_email(
    booking
):

    try:

        if not RESEND_API_KEY:

            print(
                "RESEND API KEY NOT CONFIGURED"
            )

            return False

        customer_email = (
            booking.get("email", "")
            .strip()
        )

        if not customer_email:

            print(
                "CUSTOMER EMAIL IS EMPTY"
            )

            return False

        email_data = {

            "from":
                "Velora Unisex Hair Studio "
                "<onboarding@resend.dev>",

            "to": [
                customer_email
            ],

            "subject":
                "Appointment Confirmed - "
                "Velora Unisex Hair Studio",

            "html": f"""
            <div style="
                font-family: Arial, sans-serif;
                max-width: 650px;
                margin: 30px auto;
                padding: 30px;
                border: 1px solid #e5e5e5;
                border-radius: 12px;
                background: #ffffff;
                color: #222222;
            ">

                <h2 style="
                    margin-bottom: 10px;
                ">
                    Appointment Confirmed
                </h2>

                <p>
                    Hello
                    <strong>{booking["name"]}</strong>,
                </p>

                <p>
                    Your appointment has been
                    successfully confirmed at
                    <strong>
                        Velora Unisex Hair Studio
                    </strong>.
                </p>

                <hr>

                <h3>
                    Appointment Details
                </h3>

                <p>
                    <strong>Service:</strong>
                    {booking["service"]}
                </p>

                <p>
                    <strong>Barber / Stylist:</strong>
                    {booking["stylist"]}
                </p>

                <p>
                    <strong>Date:</strong>
                    {booking["date"]}
                </p>

                <p>
                    <strong>Time:</strong>
                    {booking["time"]}
                </p>

                <p>
                    <strong>Duration:</strong>
                    {booking["duration_minutes"]}
                    minutes
                </p>

                <p>
                    <strong>Price:</strong>
                    ₹{booking["service_price"]}
                </p>

                <hr>

                <p>
                    We look forward to seeing you.
                </p>

                <p>
                    Regards,<br>
                    <strong>
                        Velora Unisex Hair Studio
                    </strong>
                </p>

            </div>
            """
        }

        response = resend.Emails.send(
            email_data
        )

        print(
            "CUSTOMER CONFIRMATION EMAIL SENT:",
            customer_email
        )

        print(
            "RESEND RESPONSE:",
            response
        )

        return True

    except Exception as error:

        print(
            "CUSTOMER EMAIL ERROR:",
            repr(error)
        )

        return False


# =========================================================
# BARBER / STYLIST EMAIL ROUTING - RESEND
# =========================================================

def send_barber_notification_email(
    booking
):
    """
    Send appointment notification ONLY
    to the selected barber/stylist.
    """

    try:

        if not RESEND_API_KEY:

            print(
                "RESEND API KEY NOT CONFIGURED"
            )

            return False

        # =================================================
        # ACTUAL STYLIST EMAILS
        # =================================================

        BARBER_EMAILS = {

            "Arjun":
                "swaminathji170@gmail.com",

            "Karan":
                "ranvjbundela48@gmail.com",

            "Riya":
                "swaminathji170@gmail.com",

            "Meera":
                "ranvjbundela48@gmail.com"

        }

        selected_barber = (
            booking["stylist"]
        )

        barber_email = BARBER_EMAILS.get(
            selected_barber
        )

        # -------------------------------------------------
        # EMAIL NOT CONFIGURED
        # -------------------------------------------------

        if not barber_email:

            print(
                "BARBER EMAIL NOT CONFIGURED FOR:",
                selected_barber
            )

            return False

        # -------------------------------------------------
        # SEND ONLY TO SELECTED BARBER
        # -------------------------------------------------

        email_data = {

            "from":
                "Velora Unisex Hair Studio "
                "<onboarding@resend.dev>",

            "to": [
                barber_email
            ],

            "subject":
                "New Appointment - "
                f"{selected_barber}",

            "html": f"""
            <div style="
                font-family: Arial, sans-serif;
                max-width: 650px;
                margin: 30px auto;
                padding: 30px;
                border: 1px solid #e5e5e5;
                border-radius: 12px;
                background: #ffffff;
                color: #222222;
            ">

                <h2>
                    New Appointment
                </h2>

                <p>
                    A new appointment has been
                    assigned to you.
                </p>

                <hr>

                <h3>
                    Customer Details
                </h3>

                <p>
                    <strong>Name:</strong>
                    {booking["name"]}
                </p>

                <p>
                    <strong>Phone:</strong>
                    {booking["phone"]}
                </p>

                <p>
                    <strong>Email:</strong>
                    {booking["email"]}
                </p>

                <hr>

                <h3>
                    Appointment Details
                </h3>

                <p>
                    <strong>Service:</strong>
                    {booking["service"]}
                </p>

                <p>
                    <strong>Date:</strong>
                    {booking["date"]}
                </p>

                <p>
                    <strong>Time:</strong>
                    {booking["time"]}
                </p>

                <p>
                    <strong>Duration:</strong>
                    {booking["duration_minutes"]}
                    minutes
                </p>

                <p>
                    <strong>Price:</strong>
                    ₹{booking["service_price"]}
                </p>

                <hr>

                <p>
                    Please be ready for the appointment.
                </p>

                <p>
                    Regards,<br>
                    <strong>
                        Velora Unisex Hair Studio
                    </strong>
                </p>

            </div>
            """
        }

        response = resend.Emails.send(
            email_data
        )

        print(
            "BARBER EMAIL SENT:",
            selected_barber,
            barber_email
        )

        print(
            "RESEND RESPONSE:",
            response
        )

        return True

    except Exception as error:

        print(
            "BARBER EMAIL ERROR:",
            repr(error)
        )

        return False

# =========================================================
# BOOK APPOINTMENT
# =========================================================

@app.route(
    "/book",
    methods=["POST"]
)
def book():

    try:

        # -------------------------------------------------
        # JSON OR FORM DATA
        # -------------------------------------------------

        payload = (
            request.get_json(
                silent=True
            )
            or request.form
        )

        # -------------------------------------------------
        # READ FORM DATA
        # -------------------------------------------------

        name = payload.get(
            "name",
            ""
        ).strip()

        phone = payload.get(
            "phone",
            ""
        ).strip()

        email = payload.get(
            "email",
            ""
        ).strip().lower()

        service = payload.get(
            "service",
            ""
        ).strip()

        stylist = payload.get(
            "stylist",
            ""
        ).strip()

        appointment_date = payload.get(
            "date",
            ""
        ).strip()

        appointment_time = payload.get(
            "time",
            ""
        ).strip()

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not all([
            name,
            phone,
            email,
            service,
            stylist,
            appointment_date,
            appointment_time
        ]):

            return jsonify({

                "ok": False,

                "code": "VALIDATION",

                "message":
                    "Please fill in all "
                    "appointment details."

            }), 400

        # -------------------------------------------------
        # VALID SERVICE
        # -------------------------------------------------

        service_price = SERVICE_PRICES.get(
            service
        )

        service_duration = SERVICE_DURATIONS.get(
            service
        )

        if service_price is None:

            return jsonify({

                "ok": False,

                "code": "SERVICE",

                "message":
                    "Please select a valid service."

            }), 400

        if service_duration is None:

            return jsonify({

                "ok": False,

                "code": "DURATION",

                "message":
                    "Service duration could not be determined."

            }), 400

        # -------------------------------------------------
        # APPOINTMENT TIME VALIDATION
        # -------------------------------------------------

        is_valid, validation_message, \
        start_datetime, end_datetime = (
            validate_booking_time(
                appointment_date,
                appointment_time,
                service
            )
        )

        if not is_valid:

            return jsonify({

                "ok": False,

                "code": "TIME",

                "message": validation_message

            }), 400

        # -------------------------------------------------
        # POCKETBASE CONFIGURATION
        # -------------------------------------------------

        if not POCKETBASE_URL:

            return jsonify({

                "ok": False,

                "code": "DATABASE",

                "message":
                    "PocketBase is not configured."

            }), 500

        # -------------------------------------------------
        # FINAL AVAILABILITY CHECK
        # -------------------------------------------------
        # This is important because another customer
        # could book the same slot after frontend
        # availability was checked.
        # -------------------------------------------------

        try:

            existing_bookings = (
                get_pocketbase_bookings(
                    appointment_date,
                    stylist
                )
            )

        except Exception as error:

            print(
                "POCKETBASE AVAILABILITY ERROR:",
                repr(error)
            )

            return jsonify({

                "ok": False,

                "code": "DATABASE",

                "message":
                    "Could not check appointment "
                    "availability. Please try again."

            }), 500

        # -------------------------------------------------
        # OVERLAP / COLLISION CHECK
        # -------------------------------------------------

        if has_booking_overlap(
            start_datetime,
            end_datetime,
            existing_bookings
        ):

            return jsonify({

                "ok": False,

                "code": "BOOKED",

                "message":
                    "This time is already booked "
                    "for the selected stylist. "
                    "Please choose another time."

            }), 409

        # -------------------------------------------------
        # BOOKING DATA
        # -------------------------------------------------

        booking_data = {

        "name": name,

        "phone": phone,

        "email": email,

        "service": service,

        "service_price": service_price,

        "duration_minutes": service_duration,

        "stylist": stylist,

        "booking_date": appointment_date,

        "start_time": appointment_time,

        "end_time": end_datetime.strftime("%H:%M"),

        "status": "confirmed",

        "created_at":
            datetime.now(
                INDIA_TIME_ZONE
            ).isoformat()
    }

        # -------------------------------------------------
        # SAVE TO POCKETBASE
        # -------------------------------------------------

        url = (
            f"{POCKETBASE_URL}"
            f"/api/collections/"
            f"{POCKETBASE_COLLECTION}"
            f"/records"
        )

        response = requests.post(

            url,

            headers=pocketbase_headers(),

            json=booking_data,

            timeout=20

        )

        print(
            "POCKETBASE BOOKING STATUS:",
            response.status_code
        )

        print(
            "POCKETBASE BOOKING RESPONSE:",
            response.text
        )

        # -------------------------------------------------
        # POCKETBASE SAVE FAILED
        # -------------------------------------------------

        if not response.ok:

            return jsonify({

                "ok": False,

                "code": "DATABASE_SAVE",

                "message":
                    "Appointment could not be saved. "
                    "Please try again."

            }), 500

        # -------------------------------------------------
        # CREATE EMAIL BOOKING OBJECT
        # -------------------------------------------------

        booking = {

            "name":
                name,

            "phone":
                phone,

            "email":
                email,

            "service":
                service,

            "service_price":
                service_price,

            "duration_minutes":
                service_duration,

            "stylist":
                stylist,

            "booking_date": appointment_date,

            "start_time": appointment_time,

            "end_time": end_datetime.strftime("%H:%M"),

            "status": "confirmed",

        }

        # -------------------------------------------------
        # SEND CUSTOMER EMAIL
        # -------------------------------------------------

        customer_email_sent = (
            send_customer_confirmation_email(
                booking
            )
        )

        # -------------------------------------------------
        # SEND SELECTED STYLIST EMAIL
        # -------------------------------------------------

        stylist_email_sent = (
            send_barber_notification_email(
                booking
            )
        )

        # -------------------------------------------------
        # FINAL SUCCESS RESPONSE
        # -------------------------------------------------

        return jsonify({

            "ok": True,

            "success": True,

            "message":
                "Appointment booked successfully.",

            "booking": {

                "name":
                    name,

                "service":
                    service,

                "service_price":
                    service_price,

                "duration_minutes":
                    service_duration,

                "stylist":
                    stylist,

                "date":
                    appointment_date,

                "time":
                    appointment_time

            },

            "customer_email_sent":
                customer_email_sent,

            "stylist_email_sent":
                stylist_email_sent

        }), 200

    except requests.RequestException as error:

        print(
            "REQUEST ERROR:",
            repr(error)
        )

        return jsonify({

            "ok": False,

            "code": "REQUEST_ERROR",

            "message":
                "A server connection error occurred. "
                "Please try again."

        }), 500

    except Exception as error:

        print(
            "BOOKING ERROR:",
            repr(error)
        )

        return jsonify({

            "ok": False,

            "code": "SERVER_ERROR",

            "message":
                "Something went wrong while "
                "booking the appointment."

        }), 500


# =========================================================
# ADMIN
# =========================================================

@app.route("/admin")
def admin():

    appointments = []

    try:

        if POCKETBASE_URL:

            url = (

                f"{POCKETBASE_URL.rstrip('/')}"

                f"/api/collections/"

                f"{POCKETBASE_COLLECTION}"

                f"/records"

            )

            params = {

                "sort": "-created",

                "perPage": 200,

                "page": 1

            }

            response = requests.get(

                url,

                headers=pocketbase_headers(),

                params=params,

                timeout=15

            )

            print(
                "POCKETBASE ADMIN STATUS:",
                response.status_code
            )

            response.raise_for_status()

            data = response.json()

            appointments = data.get(
                "items",
                []
            )

            # -------------------------------------------------
            # Template compatibility
            # -------------------------------------------------

            for appointment in appointments:

                appointment["duration"] = (
                    appointment.get(
                        "duration_minutes"
                    )
                )

    except Exception as error:

        print(
            "ADMIN POCKETBASE ERROR:",
            repr(error)
        )

        flash(
            "Unable to load appointments.",
            "error"
        )

    return render_template_string(

        ADMIN_HTML,

        appointments=appointments

    )


# =========================================================
# CLEAR APPOINTMENTS
# =========================================================

@app.route(
    "/admin/clear",
    methods=["POST"]
)
def clear_appointments():

    if not POCKETBASE_URL:

        flash(
            "PocketBase is not configured.",
            "error"
        )

        return redirect(
            url_for("admin")
        )

    try:

        # -------------------------------------------------
        # GET BOOKINGS
        # -------------------------------------------------

        url = (

            f"{POCKETBASE_URL.rstrip('/')}"

            f"/api/collections/"

            f"{POCKETBASE_COLLECTION}"

            f"/records"

        )

        params = {

            "perPage": 200,

            "page": 1

        }

        response = requests.get(

            url,

            headers=pocketbase_headers(),

            params=params,

            timeout=15

        )

        response.raise_for_status()

        data = response.json()

        records = data.get(
            "items",
            []
        )

        deleted_count = 0

        # -------------------------------------------------
        # DELETE EACH RECORD
        # -------------------------------------------------

        for record in records:

            record_id = record.get(
                "id"
            )

            if not record_id:
                continue

            delete_url = (

                f"{POCKETBASE_URL.rstrip('/')}"

                f"/api/collections/"

                f"{POCKETBASE_COLLECTION}"

                f"/records/"

                f"{record_id}"

            )

            delete_response = requests.delete(

                delete_url,

                headers=pocketbase_headers(),

                timeout=15

            )

            if delete_response.status_code in (
                200,
                204
            ):

                deleted_count += 1

        flash(

            f"{deleted_count} appointment(s) cleared.",

            "success"

        )

    except Exception as error:

        print(
            "CLEAR APPOINTMENTS ERROR:",
            repr(error)
        )

        flash(
            "Unable to clear appointments.",
            "error"
        )

    return redirect(
        url_for("admin")
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    print("=" * 55)

    print(
        "VELORA UNISEX HAIR STUDIO"
    )

    print("=" * 55)

    print(
        "Website : "
        "http://127.0.0.1:5000"
    )

    print(
        "Admin   : "
        "http://127.0.0.1:5000/admin"
    )

    print(
        "Storage : PocketBase"
    )

    print(
        "Booking : PocketBase"
    )

    print(
        "Availability : PocketBase"
    )

    print(
        "Shop Time : 10:00 AM - 08:00 PM"
    )

    print(
        "First Slot : 10:30 AM"
    )

    print(
        "Slot Interval : 15 minutes"
    )

    print("=" * 55)

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )

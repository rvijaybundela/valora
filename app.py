import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import resend
from dotenv import load_dotenv
from flask import (
    Flask, request, redirect, url_for, flash,
    render_template_string, jsonify
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "unisex-salon-secret-key")

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "").strip().rstrip("/")
POCKETBASE_COLLECTION = os.getenv("POCKETBASE_COLLECTION", "bookings").strip()
POCKETBASE_TOKEN = os.getenv("POCKETBASE_TOKEN", "").strip()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

INDIA_TIME_ZONE = ZoneInfo("Asia/Kolkata")

SHOP_OPEN_TIME = "10:00"
SHOP_CLOSE_TIME = "20:00"
FIRST_BOOKING_TIME = "10:30"
LAST_BOOKING_TIME = "19:30"
SLOT_INTERVAL_MINUTES = 15
MAX_BOOKING_DAYS = 7  # today + next 7 days

# ---------------------------------------------------------
# DATA
# ---------------------------------------------------------

MEN_SERVICES = [
    {"name": "Classic Haircut", "description": "Precision cut with styling", "price": 299, "duration": 30, "icon": "✂️"},
    {"name": "Premium Haircut", "description": "Cut, wash, massage & styling", "price": 499, "duration": 45, "icon": "💇"},
    {"name": "Beard Styling", "description": "Shape, trim & finishing", "price": 199, "duration": 20, "icon": "🧔"},
    {"name": "Hair + Beard Combo", "description": "Complete grooming experience", "price": 599, "duration": 50, "icon": "✨"},
    {"name": "Hair Spa", "description": "Deep nourishment & relaxation", "price": 799, "duration": 45, "icon": "🧖"},
    {"name": "Hair Coloring", "description": "Professional color treatment", "price": 999, "duration": 40, "icon": "🎨"},
]

WOMEN_SERVICES = [
    {"name": "Women's Haircut", "description": "Modern cut with professional styling", "price": 599, "duration": 45, "icon": "✂️"},
    {"name": "Women's Hair Spa", "description": "Relaxing nourishment treatment", "price": 899, "duration": 60, "icon": "🧖"},
    {"name": "Global Hair Color", "description": "Premium full hair coloring", "price": 1999, "duration": 90, "icon": "🎨"},
    {"name": "Highlights", "description": "Beautiful customized highlights", "price": 1499, "duration": 90, "icon": "✨"},
    {"name": "Keratin Treatment", "description": "Smooth and glossy finish", "price": 2499, "duration": 120, "icon": "💎"},
    {"name": "Bridal Styling", "description": "Elegant event & bridal styling", "price": 2999, "duration": 90, "icon": "👰"},
]

ALL_SERVICES = MEN_SERVICES + WOMEN_SERVICES
SERVICE_PRICES = {s["name"]: s["price"] for s in ALL_SERVICES}
SERVICE_DURATIONS = {s["name"]: s["duration"] for s in ALL_SERVICES}

STYLISTS = [
    {"id": "arjun", "name": "Arjun", "specialty": "Men's Grooming", "email": "swaminathji170@gmail.com"},
    {"id": "karan", "name": "Karan", "specialty": "Men's Styling", "email": "ranvjbundela48@gmail.com"},
    {"id": "riya", "name": "Riya", "specialty": "Women's Styling", "email": "swaminathji170@gmail.com"},
    {"id": "meera", "name": "Meera", "specialty": "Hair & Beauty", "email": "ranvjbundela48@gmail.com"},
]
STYLIST_EMAILS = {s["name"]: s["email"] for s in STYLISTS}

# ---------------------------------------------------------
# HTML
# ---------------------------------------------------------

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
  theme: { extend: { fontFamily: { sans: ["Inter", "sans-serif"], serif: ["Playfair Display", "serif"] } } }
}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@500;600;700&display=swap" rel="stylesheet">
<style>
html { scroll-behavior: smooth; }
body { font-family: "Inter", sans-serif; }
.serif { font-family: "Playfair Display", serif; }
.time-slots { max-height: 0; overflow: hidden; transition: max-height .3s ease; }
.time-slots.open { max-height: 420px; }
.time-slot { transition: all .2s ease; }
.time-slot:hover { transform: translateY(-1px); }
.service-card { transition: transform .3s ease, box-shadow .3s ease, border-color .3s ease; }
.service-card:hover { transform: translateY(-4px); }
.hero-image { transition: transform .7s ease; }
.hero-image:hover { transform: scale(1.02); }
</style>
</head>

<body class="bg-[#F8F5EF] text-[#242424] dark:bg-[#111111] dark:text-white transition-colors duration-300">

{% set field = "w-full px-4 py-3.5 rounded-xl bg-[#F8F5EF] dark:bg-[#151515] border border-black/10 dark:border-white/10 outline-none focus:border-[#C9A227] transition" %}
{% set label = "block text-sm font-semibold mb-2" %}
{% set eyebrow = "text-[#C9A227] text-sm uppercase tracking-[0.2em] font-semibold" %}

{% macro service_grid(services) %}
<div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
  {% for s in services %}
  <div class="service-card rounded-2xl border border-black/10 dark:border-white/10 bg-white/70 dark:bg-white/[0.04] p-6">
    <div class="flex justify-between gap-4">
      <div>
        <div class="w-12 h-12 rounded-xl bg-[#C9A227]/10 flex items-center justify-center text-2xl mb-5">{{ s.icon }}</div>
        <h4 class="font-semibold text-lg">{{ s.name }}</h4>
        <p class="text-sm opacity-55 mt-2 leading-6">{{ s.description }}</p>
      </div>
      <div class="text-right shrink-0">
        <div class="text-xl font-bold text-[#C9A227]">₹{{ s.price }}</div>
        <div class="text-xs opacity-50 mt-1">{{ s.duration }} min</div>
      </div>
    </div>
    <button type="button" data-service="{{ s.name }}" onclick="selectService(this.dataset.service)"
      class="mt-6 text-sm font-semibold hover:text-[#C9A227] transition">Book this service →</button>
  </div>
  {% endfor %}
</div>
{% endmacro %}

<!-- NAVBAR -->
<header class="sticky top-0 z-50 bg-[#F8F5EF]/95 dark:bg-[#111111]/95 backdrop-blur-xl border-b border-black/10 dark:border-white/10">
  <div class="max-w-7xl mx-auto px-5 lg:px-8">
    <div class="h-20 flex items-center justify-between">
      <a href="#home" class="flex items-center gap-3">
        <div class="w-11 h-11 rounded-full bg-[#C9A227] text-white flex items-center justify-center font-bold text-lg">V</div>
        <div>
          <div class="serif text-xl font-semibold">Velora</div>
          <div class="text-[10px] tracking-[0.25em] uppercase opacity-60">Unisex Hair Studio</div>
        </div>
      </a>
      <nav class="hidden md:flex items-center gap-8 text-sm font-medium">
        <a href="#home" class="hover:text-[#C9A227] transition">Home</a>
        <a href="#services" class="hover:text-[#C9A227] transition">Services</a>
        <a href="#about" class="hover:text-[#C9A227] transition">About</a>
        <a href="#booking" class="hover:text-[#C9A227] transition">Booking</a>
      </nav>
      <div class="flex items-center gap-3">
        <button id="themeToggle" type="button" aria-label="Toggle theme"
          class="w-10 h-10 rounded-full border border-black/10 dark:border-white/10 flex items-center justify-center hover:border-[#C9A227] transition">☾</button>
        <a href="#booking"
          class="hidden sm:inline-flex px-5 py-3 rounded-full bg-[#242424] text-white dark:bg-white dark:text-[#242424] text-sm font-semibold hover:bg-[#C9A227] dark:hover:bg-[#C9A227] dark:hover:text-white transition">Book Appointment</a>
      </div>
    </div>
  </div>
</header>

{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}
<div class="max-w-7xl mx-auto px-5 lg:px-8 pt-5">
  {% for category, message in messages %}
  <div class="mb-3 rounded-xl px-4 py-3 text-sm font-medium {% if category == 'success' %}bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200{% else %}bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200{% endif %}">{{ message }}</div>
  {% endfor %}
</div>
{% endif %}
{% endwith %}

<!-- HERO -->
<section id="home" class="relative overflow-hidden">
  <div class="max-w-7xl mx-auto px-5 lg:px-8 py-16 lg:py-24">
    <div class="grid lg:grid-cols-2 gap-12 items-center">
      <div>
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#C9A227]/30 bg-[#C9A227]/10 text-[#8f7110] dark:text-[#E3C85A] text-xs font-semibold uppercase tracking-wider">
          <span class="w-2 h-2 rounded-full {% if salon_open %}bg-green-500{% else %}bg-red-500{% endif %}"></span>
          {% if salon_open %}Open Now{% else %}Currently Closed{% endif %}
        </div>
        <h1 class="serif text-5xl md:text-6xl lg:text-7xl leading-tight mt-6">
          Your Style.<br><span class="text-[#C9A227]">Your Identity.</span>
        </h1>
        <p class="mt-6 text-base md:text-lg opacity-65 max-w-xl leading-8">
          Premium grooming and beauty services designed around your personal style, comfort and confidence.
        </p>
        <div class="flex flex-wrap gap-4 mt-8">
          <a href="#booking" class="px-6 py-3.5 rounded-full bg-[#242424] text-white dark:bg-white dark:text-[#242424] font-semibold hover:bg-[#C9A227] dark:hover:bg-[#C9A227] dark:hover:text-white transition">Book Appointment →</a>
          <a href="#services" class="px-6 py-3.5 rounded-full border border-black/10 dark:border-white/10 font-semibold hover:border-[#C9A227] transition">Explore Services</a>
        </div>
      </div>
      <div class="relative">
        <div class="absolute -inset-5 bg-[#C9A227]/10 blur-3xl rounded-full"></div>
        <img class="hero-image relative w-full h-[520px] object-cover rounded-[2rem] shadow-2xl"
          src="https://images.unsplash.com/photo-1521590832167-7bcbfaa6381f?auto=format&fit=crop&w=1200&q=85" alt="Velora Hair Studio">
      </div>
    </div>
  </div>
</section>

<!-- SERVICES -->
<section id="services" class="py-20">
  <div class="max-w-7xl mx-auto px-5 lg:px-8">
    <div class="max-w-2xl mb-12">
      <p class="{{ eyebrow }}">Our Services</p>
      <h2 class="serif text-4xl md:text-5xl mt-3">Crafted for Your Style</h2>
      <p class="mt-4 opacity-60 leading-7">Professional grooming and beauty services with transparent pricing and service duration.</p>
    </div>

    <div class="mb-14">
      <div class="flex items-center gap-4 mb-6">
        <h3 class="serif text-2xl">Men</h3>
        <div class="h-px flex-1 bg-black/10 dark:bg-white/10"></div>
      </div>
      {{ service_grid(men_services) }}
    </div>

    <div>
      <div class="flex items-center gap-4 mb-6">
        <h3 class="serif text-2xl">Women</h3>
        <div class="h-px flex-1 bg-black/10 dark:bg-white/10"></div>
      </div>
      {{ service_grid(women_services) }}
    </div>
  </div>
</section>

<!-- ABOUT -->
<section id="about" class="py-20 border-y border-black/5 dark:border-white/5">
  <div class="max-w-7xl mx-auto px-5 lg:px-8">
    <div class="grid lg:grid-cols-2 gap-12 items-center">
      <img src="https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=1200&q=85"
        alt="Professional salon" class="w-full h-[460px] object-cover rounded-[2rem]">
      <div>
        <p class="{{ eyebrow }}">About Velora</p>
        <h2 class="serif text-4xl md:text-5xl mt-3">More Than a Haircut</h2>
        <p class="mt-6 opacity-65 leading-8">
          At Velora Unisex Hair Studio, we combine professional techniques, premium products
          and a comfortable environment to create a grooming experience that feels personal.
        </p>
        <div class="grid grid-cols-2 gap-5 mt-8">
          <div class="p-5 rounded-2xl border border-black/10 dark:border-white/10">
            <div class="text-2xl font-bold text-[#C9A227]">10 AM</div>
            <div class="text-sm opacity-55 mt-1">Opening Time</div>
          </div>
          <div class="p-5 rounded-2xl border border-black/10 dark:border-white/10">
            <div class="text-2xl font-bold text-[#C9A227]">8 PM</div>
            <div class="text-sm opacity-55 mt-1">Closing Time</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- BOOKING -->
<section id="booking" class="py-20">
  <div class="max-w-4xl mx-auto px-5 lg:px-8">
    <div class="text-center mb-10">
      <p class="{{ eyebrow }}">Appointment</p>
      <h2 class="serif text-4xl md:text-5xl mt-3">Book Your Visit</h2>
      <p class="mt-4 opacity-60">Select your service, stylist and preferred time.</p>
    </div>

    <form id="bookingForm" action="{{ url_for('book') }}" method="POST"
      class="rounded-[2rem] bg-white dark:bg-white/[0.04] border border-black/10 dark:border-white/10 p-6 md:p-8 shadow-xl">
      <div class="grid md:grid-cols-2 gap-5">

        <div>
          <label class="{{ label }}">Full Name</label>
          <input type="text" name="name" required autocomplete="name" placeholder="Enter your name" class="{{ field }}">
        </div>

        <div>
          <label class="{{ label }}">Phone Number</label>
          <input type="tel" name="phone" required autocomplete="tel" placeholder="Enter phone number" class="{{ field }}">
        </div>

        <div>
          <label class="{{ label }}">Email</label>
          <input type="email" name="email" autocomplete="email" placeholder="Enter email address" class="{{ field }}">
        </div>

        <div>
          <label class="{{ label }}">Category</label>
          <select id="audienceSelect" name="audience" required class="{{ field }}">
            <option value="">Select category</option>
            <option value="men">Men</option>
            <option value="women">Women</option>
          </select>
        </div>

        <div>
          <label class="{{ label }}">Service</label>
          <select id="serviceSelect" name="service" required class="{{ field }}">
            <option value="">Choose a service</option>
            {% for s in men_services %}
            <option value="{{ s.name }}" data-category="men">{{ s.name }} — ₹{{ s.price }} · {{ s.duration }} min</option>
            {% endfor %}
            {% for s in women_services %}
            <option value="{{ s.name }}" data-category="women">{{ s.name }} — ₹{{ s.price }} · {{ s.duration }} min</option>
            {% endfor %}
          </select>
        </div>

        <div>
          <label class="{{ label }}">Stylist</label>
          <select name="stylist" required class="{{ field }}">
            <option value="">Choose stylist</option>
            {% for st in stylists %}
            <option value="{{ st.name }}">{{ st.name }}</option>
            {% endfor %}
          </select>
        </div>

        <div>
          <label class="{{ label }}">Appointment Date</label>
          <input id="appointmentDate" type="date" name="date" required class="{{ field }}">
        </div>

        <div>
          <label class="{{ label }}">Appointment Time</label>
          <button id="timePickerToggle" type="button" class="{{ field }} text-left">Choose a time</button>
          <input id="appointmentTime" type="hidden" name="time" required>
          <div id="timeSlots" class="time-slots mt-3 grid grid-cols-3 sm:grid-cols-4 gap-2"></div>
        </div>

      </div>

      <div id="availabilityMessage" class="hidden mt-5 rounded-xl px-4 py-3 text-sm font-semibold"></div>

      <button type="submit"
        class="w-full mt-6 px-6 py-4 rounded-xl bg-[#242424] text-white dark:bg-white dark:text-[#242424] font-semibold hover:bg-[#C9A227] dark:hover:bg-[#C9A227] dark:hover:text-white transition">
        Confirm Appointment →
      </button>
    </form>
  </div>
</section>

<!-- FOOTER -->
<footer class="border-t border-black/10 dark:border-white/10">
  <div class="max-w-7xl mx-auto px-5 lg:px-8 py-10">
    <div class="grid md:grid-cols-3 gap-8">
      <div>
        <div class="serif text-2xl font-semibold">Velora</div>
        <p class="text-sm opacity-55 mt-2">Unisex Hair Studio</p>
      </div>
      <div>
        <h4 class="font-semibold mb-3">Opening Hours</h4>
        <p class="text-sm opacity-60">Every Day</p>
        <p class="text-sm opacity-60 mt-1">10:00 AM — 8:00 PM</p>
      </div>
      <div>
        <h4 class="font-semibold mb-3">Quick Links</h4>
        <div class="flex flex-col gap-2 text-sm opacity-60">
          <a href="#services" class="hover:text-[#C9A227]">Services</a>
          <a href="#about" class="hover:text-[#C9A227]">About</a>
          <a href="#booking" class="hover:text-[#C9A227]">Booking</a>
        </div>
      </div>
    </div>
  </div>
</footer>

<script>
const MSG_BASE = "mt-4 rounded-xl px-4 py-3 text-sm font-semibold ";
const MSG_STYLES = {
  info: "bg-black/5 text-black/70 dark:bg-white/10 dark:text-white/70",
  ok: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200",
  error: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200"
};

document.addEventListener("DOMContentLoaded", () => {
  const $ = id => document.getElementById(id);
  const themeToggle = $("themeToggle");
  const serviceSelect = $("serviceSelect");
  const audienceSelect = $("audienceSelect");
  const stylistInput = document.querySelector('select[name="stylist"]');
  const dateInput = $("appointmentDate");
  const timeInput = $("appointmentTime");
  const timePickerToggle = $("timePickerToggle");
  const timeSlots = $("timeSlots");
  const msg = $("availabilityMessage");
  let availabilityRequest = null;

  function showMessage(text, type) {
    msg.textContent = text;
    msg.className = MSG_BASE + MSG_STYLES[type];
  }

  function clearSlotSelection() {
    timeSlots.querySelectorAll(".time-slot").forEach(b =>
      b.classList.remove("selected", "bg-[#C9A227]", "text-white"));
  }

  // THEME
  try {
    if (localStorage.getItem("velora-theme") === "dark") {
      document.documentElement.classList.add("dark");
      themeToggle.textContent = "☀";
    }
  } catch (e) {}

  themeToggle.addEventListener("click", () => {
    document.documentElement.classList.toggle("dark");
    const isDark = document.documentElement.classList.contains("dark");
    try { localStorage.setItem("velora-theme", isDark ? "dark" : "light"); } catch (e) {}
    themeToggle.textContent = isDark ? "☀" : "☾";
  });

  // DATE RANGE: today .. today + 7 days
  const toISO = d => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split("T")[0];
  const now = new Date();
  const maxDate = new Date(now.getTime() + 7 * 86400000);
  dateInput.min = toISO(now);
  dateInput.max = toISO(maxDate);

  // TIME SLOTS: 10:30 AM - 7:30 PM (matches backend)
  for (let minutes = 630; minutes <= 1170; minutes += 15) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    const displayHour = hours > 12 ? hours - 12 : hours;
    const label = `${displayHour}:${String(mins).padStart(2, "0")} ${hours >= 12 ? "PM" : "AM"}`;
    const value = `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "time-slot px-3 py-2.5 rounded-lg border border-black/10 dark:border-white/10 text-sm font-medium hover:border-[#C9A227] transition";
    button.textContent = label;
    button.dataset.value = value;

    button.addEventListener("click", () => {
      timeInput.value = value;
      timePickerToggle.textContent = label;
      clearSlotSelection();
      button.classList.add("selected", "bg-[#C9A227]", "text-white");
      timeSlots.classList.remove("open");
      checkAvailability();
    });

    timeSlots.appendChild(button);
  }

  timePickerToggle.addEventListener("click", () => timeSlots.classList.toggle("open"));

  // SERVICE -> CATEGORY
  serviceSelect.addEventListener("change", () => {
    const option = serviceSelect.options[serviceSelect.selectedIndex];
    if (option && option.dataset.category) {
      audienceSelect.value = option.dataset.category;
    }
  });

  // AVAILABILITY
  async function checkAvailability() {
    const date = dateInput.value;
    const time = timeInput.value;
    const stylist = stylistInput.value;
    const service = serviceSelect.value;

    if (!date || !time || !stylist || !service) {
      msg.classList.add("hidden");
      return;
    }

    if (availabilityRequest) availabilityRequest.abort();
    availabilityRequest = new AbortController();

    showMessage("Checking availability...", "info");
    msg.classList.remove("hidden");

    try {
      const params = new URLSearchParams({ date, time, stylist, service });
      const response = await fetch(`/availability?${params}`, { signal: availabilityRequest.signal });
      const result = await response.json();
      showMessage(
        result.message || (result.available ? "This time is available." : "This time is not available."),
        result.available ? "ok" : "error"
      );
    } catch (error) {
      if (error.name === "AbortError") return;
      showMessage("Availability could not be checked. Please try again.", "error");
    }
  }

  [dateInput, stylistInput, serviceSelect].forEach(el =>
    el.addEventListener("change", checkAvailability));

  // BOOKING SUBMIT
  $("bookingForm").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = form.querySelector('button[type="submit"]');

    if (!timeInput.value) {
      showMessage("Please choose an appointment time.", "error");
      msg.classList.remove("hidden");
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Confirming...";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "Accept": "application/json" }
      });
      const result = await response.json();

      showMessage(result.message || "Unable to complete booking.", result.ok ? "ok" : "error");
      msg.classList.remove("hidden");

      if (result.ok) {
        form.reset();
        timeInput.value = "";
        timePickerToggle.textContent = "Choose a time";
        timeSlots.classList.remove("open");
        clearSlotSelection();
      }
    } catch (error) {
      showMessage("Booking could not be completed. Please try again.", "error");
      msg.classList.remove("hidden");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Confirm Appointment →";
    }
  });
});

function selectService(serviceName) {
  const serviceSelect = document.getElementById("serviceSelect");
  serviceSelect.value = serviceName;
  document.getElementById("booking").scrollIntoView({ behavior: "smooth" });
  serviceSelect.dispatchEvent(new Event("change"));
}
</script>

</body>
</html>
"""

ADMIN_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Velora Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config = { darkMode: "class" }</script>
</head>

<body class="bg-[#F8F5EF] text-[#242424] dark:bg-[#111111] dark:text-white">
<div class="max-w-7xl mx-auto px-5 py-10">

  <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-5 mb-8">
    <div>
      <p class="text-xs uppercase tracking-[0.2em] text-[#C9A227] font-semibold">Velora</p>
      <h1 class="text-3xl font-bold mt-1">Appointment Dashboard</h1>
      <p class="text-sm opacity-55 mt-2">Manage salon appointments</p>
    </div>
    <div class="flex items-center gap-3">
      <div class="px-4 py-2 rounded-full bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200 text-sm font-semibold">● Database Connected</div>
      <form action="{{ url_for('clear_appointments') }}" method="POST" onsubmit="return confirm('Delete ALL appointments?');">
        <button class="px-5 py-2.5 rounded-xl bg-red-600 text-white text-sm font-semibold">Clear All</button>
      </form>
      <a href="{{ url_for('home') }}" class="px-5 py-2.5 rounded-xl bg-[#242424] text-white dark:bg-white dark:text-[#242424] text-sm font-semibold">View Website</a>
    </div>
  </div>

  {% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
  <div class="mb-4 rounded-xl px-4 py-3 text-sm font-medium {% if category == 'success' %}bg-green-100 text-green-800{% else %}bg-red-100 text-red-800{% endif %}">{{ message }}</div>
  {% endfor %}
  {% endwith %}

  <div class="rounded-2xl overflow-hidden border border-black/10 dark:border-white/10 bg-white dark:bg-white/[0.04]">
    <div class="overflow-x-auto">
      <table class="w-full text-left">
        <thead class="bg-black/[0.03] dark:bg-white/[0.04]">
          <tr>
            {% for h in ["ID", "Customer", "Phone", "Service", "Stylist", "Date", "Time"] %}
            <th class="px-5 py-4 text-xs uppercase tracking-wider opacity-60">{{ h }}</th>
            {% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for a in appointments %}
          <tr class="border-t border-black/5 dark:border-white/5 hover:bg-black/[0.02] dark:hover:bg-white/[0.02]">
            <td class="px-5 py-4 text-sm">{{ a.id }}</td>
            <td class="px-5 py-4">
              <div class="font-semibold">{{ a.name }}</div>
              {% if a.email %}<div class="text-xs opacity-50 mt-1">{{ a.email }}</div>{% endif %}
            </td>
            <td class="px-5 py-4 text-sm">{{ a.phone }}</td>
            <td class="px-5 py-4">
              <div class="font-medium">{{ a.service }}</div>
              {% if a.duration_minutes %}<div class="text-xs opacity-50 mt-1">{{ a.duration_minutes }} min</div>{% endif %}
            </td>
            <td class="px-5 py-4 text-sm">{{ a.stylist }}</td>
            <td class="px-5 py-4 text-sm">{{ a.booking_date }}</td>
            <td class="px-5 py-4 text-sm font-semibold">{{ a.start_time }}{% if a.end_time %} – {{ a.end_time }}{% endif %}</td>
          </tr>
          {% else %}
          <tr><td colspan="7" class="px-5 py-14 text-center opacity-50">No appointments found.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

</div>
</body>
</html>
"""

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def pocketbase_headers():
    headers = {"Content-Type": "application/json"}
    if POCKETBASE_TOKEN:
        headers["Authorization"] = f"Bearer {POCKETBASE_TOKEN}"
    return headers


def records_url(record_id=None):
    url = f"{POCKETBASE_URL}/api/collections/{POCKETBASE_COLLECTION}/records"
    return f"{url}/{record_id}" if record_id else url


def get_salon_status():
    now = datetime.now(INDIA_TIME_ZONE).time()
    opening = datetime.strptime(SHOP_OPEN_TIME, "%H:%M").time()
    closing = datetime.strptime(SHOP_CLOSE_TIME, "%H:%M").time()

    if opening <= now < closing:
        return {"open": True, "text": "OPEN NOW", "description": "We're open until 8:00 PM IST"}
    return {"open": False, "text": "CLOSED", "description": "Open daily from 10:00 AM IST"}


def time_to_minutes(time_string):
    hour, minute = map(int, time_string.strip().split(":"))
    return hour * 60 + minute


def get_pocketbase_bookings(appointment_date, stylist):
    """Confirmed bookings for a date and stylist."""
    if not POCKETBASE_URL:
        raise RuntimeError("POCKETBASE_URL is not configured.")

    params = {
        "filter": (
            f'booking_date="{appointment_date}" '
            f'&& stylist="{stylist}" '
            f'&& status="confirmed"'
        ),
        "perPage": 200,
        "page": 1,
    }

    response = requests.get(
        records_url(), headers=pocketbase_headers(), params=params, timeout=15
    )
    if not response.ok:
        print("POCKETBASE AVAILABILITY FAILED:", response.status_code, response.url)
        print("POCKETBASE RESPONSE:", response.text)

    response.raise_for_status()
    return response.json().get("items", [])


def has_booking_overlap(start_datetime, end_datetime, existing_bookings):
    """True if [start, end) overlaps any existing booking (compared as minutes)."""
    new_start = start_datetime.hour * 60 + start_datetime.minute
    new_end = end_datetime.hour * 60 + end_datetime.minute

    for booking in existing_bookings:
        start_text = str(booking.get("start_time", "")).strip()
        end_text = str(booking.get("end_time", "")).strip()

        if not (start_text and end_text):
            continue

        try:
            existing_start = time_to_minutes(start_text)
            existing_end = time_to_minutes(end_text)
        except (ValueError, TypeError):
            continue

        if new_start < existing_end and new_end > existing_start:
            return True

    return False


def validate_booking_time(appointment_date, appointment_time, service):
    """Returns (valid, message, start_datetime, end_datetime)."""

    def fail(message):
        return False, message, None, None

    duration = SERVICE_DURATIONS.get(service)
    if duration is None:
        return fail("Please select a valid service.")

    try:
        start = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return fail("Invalid appointment date or time.")

    now = datetime.now(INDIA_TIME_ZONE)
    today = now.date()

    if not (today <= start.date() <= today + timedelta(days=MAX_BOOKING_DAYS)):
        return fail(f"Appointments can be booked only for today through the next {MAX_BOOKING_DAYS} days.")

    first = time_to_minutes(FIRST_BOOKING_TIME)
    last = time_to_minutes(LAST_BOOKING_TIME)
    selected = start.hour * 60 + start.minute

    if selected < first:
        return fail("Bookings start from 10:30 AM.")

    if selected > last:
        return fail("The last booking start time is 7:30 PM.")

    if (selected - first) % SLOT_INTERVAL_MINUTES != 0:
        return fail("Please select a valid 15-minute time slot.")

    end = start + timedelta(minutes=int(duration))
    close = start.replace(hour=time_to_minutes(SHOP_CLOSE_TIME) // 60, minute=0, second=0, microsecond=0)

    if end > close:
        return fail(f"This service takes {duration} minutes and must finish by 8:00 PM.")

    if start.date() == today and start <= now.replace(tzinfo=None):
        return fail("This time slot has already passed.")

    return True, "", start, end


# ---------------------------------------------------------
# EMAIL
# ---------------------------------------------------------

def email_shell(title, intro, sections):
    """sections: list of (heading, [(label, value), ...])"""
    body = ""
    for heading, rows in sections:
        body += f"<hr><h3>{heading}</h3>"
        for label, value in rows:
            body += f"<p><strong>{label}:</strong> {value}</p>"

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:650px;margin:30px auto;padding:30px;
                border:1px solid #e5e5e5;border-radius:12px;background:#fff;color:#222;">
        <h2>{title}</h2>
        <p>{intro}</p>
        {body}
        <hr>
        <p>Regards,<br><strong>Velora Unisex Hair Studio</strong></p>
    </div>
    """


def send_email(to_address, subject, html):
    try:
        if not RESEND_API_KEY:
            print("RESEND API KEY NOT CONFIGURED")
            return False

        if not to_address:
            print("EMAIL RECIPIENT IS EMPTY")
            return False

        response = resend.Emails.send({
            "from": "Velora Unisex Hair Studio <onboarding@resend.dev>",
            "to": [to_address],
            "subject": subject,
            "html": html,
        })
        print("EMAIL SENT:", to_address, response)
        return True

    except Exception as error:
        print("EMAIL ERROR:", repr(error))
        return False


def appointment_rows(booking):
    return [
        ("Service", booking["service"]),
        ("Barber / Stylist", booking["stylist"]),
        ("Date", booking["booking_date"]),
        ("Time", f'{booking["start_time"]} - {booking["end_time"]}'),
        ("Duration", f'{booking["duration_minutes"]} minutes'),
        ("Price", f'₹{booking["service_price"]}'),
    ]


def send_customer_confirmation_email(booking):
    if not booking.get("email"):
        return False

    html = email_shell(
        "Appointment Confirmed",
        f'Hello <strong>{booking["name"]}</strong>, your appointment has been confirmed.',
        [("Appointment Details", appointment_rows(booking))],
    )
    return send_email(
        booking["email"],
        "Appointment Confirmed - Velora Unisex Hair Studio",
        html,
    )


def send_barber_notification_email(booking):
    stylist = booking["stylist"]
    html = email_shell(
        "New Appointment",
        "A new appointment has been assigned to you.",
        [
            ("Customer Details", [
                ("Name", booking["name"]),
                ("Phone", booking["phone"]),
                ("Email", booking["email"] or "Not provided"),
            ]),
            ("Appointment Details", appointment_rows(booking)),
        ],
    )
    return send_email(STYLIST_EMAILS.get(stylist), f"New Appointment - {stylist}", html)


# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

@app.route("/")
def home():
    status = get_salon_status()
    return render_template_string(
        INDEX_HTML,
        status=status,
        salon_open=status["open"],
        men_services=MEN_SERVICES,
        women_services=WOMEN_SERVICES,
        stylists=STYLISTS,
    )


@app.route("/test-pocketbase")
def test_pocketbase():
    if not POCKETBASE_URL:
        return jsonify({"ok": False, "step": "configuration", "message": "POCKETBASE_URL is empty."}), 500

    try:
        response = requests.get(
            records_url(),
            headers=pocketbase_headers(),
            params={"page": 1, "perPage": 1},
            timeout=10,
        )
        print("POCKETBASE TEST:", response.status_code, response.text)

        if response.ok:
            return jsonify({
                "ok": True,
                "message": "PocketBase connection successful.",
                "pocketbase_url": POCKETBASE_URL,
                "collection": POCKETBASE_COLLECTION,
                "status_code": response.status_code,
            })

        return jsonify({
            "ok": False,
            "message": "PocketBase responded with an error.",
            "status_code": response.status_code,
            "response": response.text,
        }), 500

    except Exception as error:
        print("POCKETBASE TEST ERROR:", repr(error))
        return jsonify({"ok": False, "message": "Could not connect to PocketBase.", "error": repr(error)}), 500


@app.route("/availability", methods=["GET"])
@app.route("/check-slots", methods=["GET"])
def availability():
    error_response = jsonify({
        "ok": False,
        "available": False,
        "message": "Availability could not be checked. Please try again.",
    })

    try:
        appointment_date = request.args.get("date", "").strip()
        appointment_time = request.args.get("time", "").strip()
        stylist = request.args.get("stylist", "").strip()
        service = request.args.get("service", "").strip()

        if not all([appointment_date, appointment_time, stylist, service]):
            return jsonify({
                "ok": False,
                "available": False,
                "message": "Please select date, time, service and stylist.",
            }), 400

        if service not in SERVICE_DURATIONS:
            return jsonify({"ok": False, "available": False, "message": "Invalid service selected."}), 400

        valid, message, start, end = validate_booking_time(appointment_date, appointment_time, service)

        if not valid:
            return jsonify({"ok": True, "available": False, "message": message}), 200

        if not POCKETBASE_URL:
            print("ERROR: POCKETBASE_URL is empty.")
            return jsonify({"ok": False, "available": False, "message": "PocketBase is not configured."}), 500

        try:
            existing = get_pocketbase_bookings(appointment_date, stylist)
        except Exception as error:
            print("AVAILABILITY ERROR:", repr(error))
            return error_response, 503

        if has_booking_overlap(start, end, existing):
            return jsonify({
                "ok": True,
                "available": False,
                "message": "This time slot is already booked with the selected stylist.",
            }), 200

        return jsonify({
            "ok": True,
            "available": True,
            "message": "This appointment slot is available.",
            "duration_minutes": SERVICE_DURATIONS[service],
        }), 200

    except Exception as error:
        print("AVAILABILITY ROUTE ERROR:", repr(error))
        return error_response, 500


@app.route("/book", methods=["POST"])
def book():
    def fail(code, message, status):
        return jsonify({"ok": False, "code": code, "message": message}), status

    try:
        payload = request.get_json(silent=True) or request.form

        name = payload.get("name", "").strip()
        phone = payload.get("phone", "").strip()
        email = payload.get("email", "").strip().lower()
        service = payload.get("service", "").strip()
        stylist = payload.get("stylist", "").strip()
        appointment_date = payload.get("date", "").strip()
        appointment_time = payload.get("time", "").strip()

        # Email is optional.
        if not all([name, phone, service, stylist, appointment_date, appointment_time]):
            return fail("VALIDATION", "Please fill in all appointment details.", 400)

        if stylist not in STYLIST_EMAILS:
            return fail("STYLIST", "Please select a valid stylist.", 400)

        service_price = SERVICE_PRICES.get(service)
        service_duration = SERVICE_DURATIONS.get(service)

        if service_price is None or service_duration is None:
            return fail("SERVICE", "Please select a valid service.", 400)

        valid, message, start, end = validate_booking_time(appointment_date, appointment_time, service)
        if not valid:
            return fail("TIME", message, 400)

        if not POCKETBASE_URL:
            return fail("DATABASE", "PocketBase is not configured.", 500)

        # Final check in case someone booked the slot meanwhile.
        try:
            existing = get_pocketbase_bookings(appointment_date, stylist)
        except Exception as error:
            print("AVAILABILITY ERROR:", repr(error))
            return fail("DATABASE", "Could not check appointment availability. Please try again.", 500)

        if has_booking_overlap(start, end, existing):
            return fail("BOOKED", "This time is already booked for the selected stylist. Please choose another time.", 409)

        booking = {
            "name": name,
            "phone": phone,
            "email": email,
            "service": service,
            "service_price": service_price,
            "duration_minutes": service_duration,
            "stylist": stylist,
            "booking_date": appointment_date,
            "start_time": appointment_time,
            "end_time": end.strftime("%H:%M"),
            "status": "confirmed",
            "created_at": datetime.now(INDIA_TIME_ZONE).isoformat(),
        }

        response = requests.post(
            records_url(), headers=pocketbase_headers(), json=booking, timeout=20
        )
        print("POCKETBASE BOOKING:", response.status_code, response.text)

        if not response.ok:
            return fail("DATABASE_SAVE", "Appointment could not be saved. Please try again.", 500)

        customer_email_sent = send_customer_confirmation_email(booking)
        stylist_email_sent = send_barber_notification_email(booking)

        return jsonify({
            "ok": True,
            "success": True,
            "message": "Appointment booked successfully.",
            "booking": {
                "name": name,
                "service": service,
                "service_price": service_price,
                "duration_minutes": service_duration,
                "stylist": stylist,
                "date": appointment_date,
                "time": appointment_time,
            },
            "customer_email_sent": customer_email_sent,
            "stylist_email_sent": stylist_email_sent,
        }), 200

    except requests.RequestException as error:
        print("REQUEST ERROR:", repr(error))
        return fail("REQUEST_ERROR", "A server connection error occurred. Please try again.", 500)

    except Exception as error:
        print("BOOKING ERROR:", repr(error))
        return fail("SERVER_ERROR", "Something went wrong while booking the appointment.", 500)


@app.route("/admin")
def admin():
    appointments = []

    try:
        if POCKETBASE_URL:
            response = requests.get(
                records_url(),
                headers=pocketbase_headers(),
                params={"sort": "-created", "perPage": 200, "page": 1},
                timeout=15,
            )
            response.raise_for_status()
            appointments = response.json().get("items", [])

    except Exception as error:
        print("ADMIN ERROR:", repr(error))
        flash("Unable to load appointments.", "error")

    return render_template_string(ADMIN_HTML, appointments=appointments)


@app.route("/admin/clear", methods=["POST"])
def clear_appointments():
    if not POCKETBASE_URL:
        flash("PocketBase is not configured.", "error")
        return redirect(url_for("admin"))

    try:
        response = requests.get(
            records_url(),
            headers=pocketbase_headers(),
            params={"perPage": 200, "page": 1},
            timeout=15,
        )
        response.raise_for_status()

        deleted = 0
        for record in response.json().get("items", []):
            record_id = record.get("id")
            if not record_id:
                continue

            result = requests.delete(
                records_url(record_id), headers=pocketbase_headers(), timeout=15
            )
            if result.status_code in (200, 204):
                deleted += 1

        flash(f"{deleted} appointment(s) cleared.", "success")

    except Exception as error:
        print("CLEAR ERROR:", repr(error))
        flash("Unable to clear appointments.", "error")

    return redirect(url_for("admin"))


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )

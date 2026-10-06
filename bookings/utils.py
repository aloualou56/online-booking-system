"""
Availability calculation utilities for the booking engine.
"""
from datetime import datetime, timedelta, time, date
from businesses.models import WorkingHours, SpecialDayOff, BusinessHours, BusinessDayOff
from .models import Booking


def _get_booking_gap_minutes(business):
    if getattr(business, 'booking_gap_enabled', False):
        return int(getattr(business, 'booking_gap_minutes', 0) or 0)
    return 0


def _intervals_conflict(slot_start, slot_end, booking_start, booking_end, gap_minutes):
    """Return True when two booking intervals conflict, including gap padding."""
    slot_block_end = (datetime.combine(date.min, slot_end) + timedelta(minutes=gap_minutes)).time()
    booking_block_end = (datetime.combine(date.min, booking_end) + timedelta(minutes=gap_minutes)).time()
    return slot_start < booking_block_end and slot_block_end > booking_start


def _slot_overlaps_business_break(business, slot_start, slot_end):
    """Return True when a slot overlaps the business break window."""
    if not business.break_start_time or not business.break_end_time:
        return False
    return slot_start < business.break_end_time and slot_end > business.break_start_time


def get_available_slots_capacity(business, service, target_date):
    """
    Calculate available time slots based on business capacity (no specific employee).
    Uses per-day BusinessHours if set, otherwise falls back to business defaults.
    
    Returns a list of dicts: [{'start': time, 'end': time, 'start_str': str, 'end_str': str}, ...]
    """
    day_of_week = target_date.weekday()  # 0=Monday

    # Check if business has a temporary closure for this date
    if BusinessDayOff.objects.filter(business=business, date=target_date).exists():
        return []

    # Try per-day BusinessHours first
    try:
        bh = BusinessHours.objects.get(business=business, day_of_week=day_of_week)
        if bh.is_closed:
            return []
        start_time = bh.start_time
        end_time = bh.end_time
    except BusinessHours.DoesNotExist:
        # Fall back to business defaults
        start_time = business.default_start_time
        end_time = business.default_end_time
    
    # Generate all possible slots
    slot_duration = timedelta(minutes=service.duration_minutes)
    gap_minutes = _get_booking_gap_minutes(business)
    slot_step = timedelta(minutes=service.duration_minutes + gap_minutes)
    slots = []
    
    current = datetime.combine(target_date, start_time)
    end_of_day = datetime.combine(target_date, end_time)
    
    # Get all bookings for this business on this date
    existing_bookings = Booking.objects.filter(
        business=business,
        date=target_date,
        status__in=['pending', 'confirmed'],
    ).values_list('start_time', 'end_time')
    booked_ranges = [(b[0], b[1]) for b in existing_bookings]
    
    while current + slot_duration <= end_of_day:
        slot_start = current.time()
        slot_end = (current + slot_duration).time()

        if _slot_overlaps_business_break(business, slot_start, slot_end):
            current += slot_step
            continue
        
        # Count how many bookings overlap with this slot
        overlap_count = 0
        for bk_start, bk_end in booked_ranges:
            if _intervals_conflict(slot_start, slot_end, bk_start, bk_end, gap_minutes):
                overlap_count += 1
        
        # Slot is available if we haven't reached capacity
        if overlap_count < business.hourly_capacity:
            slots.append({
                'start': slot_start,
                'end': slot_end,
                'start_str': slot_start.strftime('%H:%M'),
                'end_str': slot_end.strftime('%H:%M'),
            })
        
        current += slot_step
    
    return slots


def get_available_slots(employee, service, target_date):
    """
    Calculate available time slots for a given employee, service and date.

    Returns a list of dicts: [{'start': time, 'end': time}, ...]
    """
    # Skip inactive employees
    if not employee.is_active:
        return []

    # Check if business is closed on this date
    if BusinessDayOff.objects.filter(business=employee.business, date=target_date).exists():
        return []

    # Check if it's a special day off (only approved requests block availability)
    if SpecialDayOff.objects.filter(employee=employee, date=target_date, status='approved').exists():
        return []

    # Get working hours for the day of week
    day_of_week = target_date.weekday()  # 0=Monday
    try:
        wh = WorkingHours.objects.get(employee=employee, day_of_week=day_of_week)
    except WorkingHours.DoesNotExist:
        return []

    if wh.is_day_off:
        return []

    # Generate all possible slots
    slot_duration = timedelta(minutes=service.duration_minutes)
    gap_minutes = _get_booking_gap_minutes(employee.business)
    slot_step = timedelta(minutes=service.duration_minutes + gap_minutes)
    slots = []

    current = datetime.combine(target_date, wh.start_time)
    end_of_day = datetime.combine(target_date, wh.end_time)

    # Get existing bookings for this employee on this date
    existing_bookings = Booking.objects.filter(
        employee=employee,
        date=target_date,
        status__in=['pending', 'confirmed'],
    ).values_list('start_time', 'end_time')

    booked_ranges = [(b[0], b[1]) for b in existing_bookings]

    while current + slot_duration <= end_of_day:
        slot_start = current.time()
        slot_end = (current + slot_duration).time()

        if _slot_overlaps_business_break(employee.business, slot_start, slot_end):
            current += slot_step
            continue

        # Check if slot conflicts with existing bookings
        is_available = True
        for bk_start, bk_end in booked_ranges:
            if _intervals_conflict(slot_start, slot_end, bk_start, bk_end, gap_minutes):
                is_available = False
                break

        if is_available:
            slots.append({
                'start': slot_start,
                'end': slot_end,
                'start_str': slot_start.strftime('%H:%M'),
                'end_str': slot_end.strftime('%H:%M'),
            })

        current += slot_step

    return slots


def get_available_dates_capacity(business, service, start_date, num_days=30):
    """
    Get a list of dates with available slots based on business capacity.
    Used when business has no employees.
    
    Returns: [{'date': date, 'date_str': 'YYYY-MM-DD', 'display': str, 'day_name': str, 'slots_count': int}, ...]
    """
    available_dates = []
    for i in range(num_days):
        d = start_date + timedelta(days=i)
        slots = get_available_slots_capacity(business, service, d)
        if slots:
            available_dates.append({
                'date': d,
                'date_str': d.strftime('%Y-%m-%d'),
                'display': d.strftime('%d/%m/%Y'),
                'day_name': ['Δευ', 'Τρι', 'Τετ', 'Πεμ', 'Παρ', 'Σαβ', 'Κυρ'][d.weekday()],
                'slots_count': len(slots),
            })
    return available_dates


def get_available_dates(employee, service, start_date, num_days=30):
    """
    Get a list of dates with available slots in the next num_days.

    Returns: [{'date': date, 'date_str': 'YYYY-MM-DD', 'slots_count': int}, ...]
    """
    available_dates = []
    for i in range(num_days):
        d = start_date + timedelta(days=i)
        slots = get_available_slots(employee, service, d)
        if slots:
            available_dates.append({
                'date': d,
                'date_str': d.strftime('%Y-%m-%d'),
                'display': d.strftime('%d/%m/%Y'),
                'day_name': ['Δευ', 'Τρι', 'Τετ', 'Πεμ', 'Παρ', 'Σαβ', 'Κυρ'][d.weekday()],
                'slots_count': len(slots),
            })
    return available_dates

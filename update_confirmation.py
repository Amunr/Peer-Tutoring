from pathlib import Path
path = Path('app/templates/student/confirmation.html')
old = "        <ul class=\"list-group list-group-flush mb-3\">\n          <li class=\"list-group-item\"><strong>Student:</strong> {{ booking.student_name }}</li>\n          <li class=\"list-group-item\"><strong>Student Phone:</strong> {{ student_phone }}</li>\n          <li class=\"list-group-item\"><strong>Assigned Tutor:</strong> {{ tutor.name }}</li>\n          <li class=\"list-group-item\"><strong>Tutor Phone:</strong> {{ tutor_phone }}</li>\n        </ul>\n        <div class=\"alert alert-info\" role=\"alert\">\n          Your tutor will contact you using the phone number you provided.\n        </div>"
new = "        <ul class=\"list-group list-group-flush mb-3\">\n          <li class=\"list-group-item\"><strong>Student:</strong> {{ booking.student_name }}</li>\n          <li class=\"list-group-item\"><strong>Student Phone:</strong> {{ student_phone }}</li>\n          <li class=\"list-group-item\"><strong>Your Tutor:</strong> {{ tutor.name }} &middot; {{ tutor_phone }}</li>\n        </ul>\n        <div class=\"alert alert-info\" role=\"alert\">\n          Your tutor will contact you using the phone number you provided. If they cancel, you are welcome to schedule another appointment. If you do not hear from them soon, feel free to reach out using the contact information above.\n        </div>"
text = path.read_text()
if old not in text:
    raise SystemExit('pattern not found')
path.write_text(text.replace(old, new))

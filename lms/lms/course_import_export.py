import json
import os
import secrets
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timedelta

import frappe
from frappe import _


def export_course_zip(course_name):
	course = frappe.get_doc("LMS Course", course_name)
	chapters = get_chapters_for_export(course.chapters)
	lessons = get_lessons_for_export(course_name)
	instructors = get_course_instructors(course)
	evaluator = get_course_evaluator(course)
	assets = get_course_assets(course, lessons, instructors, evaluator)
	assessments, questions, test_cases = get_course_assessments(lessons)
	safe_time = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	zip_filename = f"{course.name}_{safe_time}_{secrets.token_hex(4)}.zip"
	create_course_zip(
		zip_filename,
		course,
		chapters,
		lessons,
		assets,
		assessments,
		questions,
		test_cases,
		instructors,
		evaluator,
	)


def get_chapters_for_export(chapters: list):
	chapters_list = []
	for row in chapters:
		chapter = frappe.get_doc("Course Chapter", row.chapter)
		chapters_list.append(chapter)
	return chapters_list


def get_lessons_for_export(course_name: str):
	lessons = frappe.get_all("Course Lesson", {"course": course_name}, pluck="name")
	lessons_list = []
	for lesson in lessons:
		lesson_doc = frappe.get_doc("Course Lesson", lesson)
		lessons_list.append(lesson_doc)
	return lessons_list


def get_course_assessments(lessons):
	assessments, questions, test_cases = [], [], []
	for lesson in lessons:
		content = json.loads(lesson.content) if lesson.content else {}
		for block in content.get("blocks", []):
			block_type = block.get("type")
			if block_type in ("quiz", "assignment", "program"):
				data_field = "exercise" if block_type == "program" else block_type
				name = block.get("data", {}).get(data_field)
				doctype = (
					"LMS Quiz"
					if block_type == "quiz"
					else ("LMS Assignment" if block_type == "assignment" else "LMS Programming Exercise")
				)
				if frappe.db.exists(doctype, name):
					doc = frappe.get_doc(doctype, name)
					assessments.append(doc.as_dict())
					if doctype == "LMS Quiz":
						for q in doc.questions:
							question_doc = frappe.get_doc("LMS Question", q.question)
							questions.append(question_doc.as_dict())
					if doctype == "LMS Programming Exercise":
						for tc in doc.test_cases:
							test_case_doc = frappe.get_doc("LMS Test Case", tc.name)
							test_cases.append(test_case_doc.as_dict())

	return assessments, questions, test_cases


def get_course_instructors(course):
	users = []
	for instructor in course.instructors:
		user_info = frappe.db.get_value(
			"User",
			instructor.instructor,
			["name", "full_name", "first_name", "last_name", "email", "user_image"],
			as_dict=True,
		)
		if user_info:
			users.append(user_info)
	return users


def get_course_evaluator(course):
	evaluators = []
	if course.evaluator and frappe.db.exists("Course Evaluator", course.evaluator):
		evaluator_info = frappe.get_doc("Course Evaluator", course.evaluator)
		evaluators.append(evaluator_info)
	return evaluators


def get_course_assets(course, lessons, instructors, evaluator):
	assets = []
	if course.image:
		assets.append(course.image)
	for lesson in lessons:
		content = json.loads(lesson.content) if lesson.content else {}
		for block in content.get("blocks", []):
			if block.get("type") == "upload":
				url = block.get("data", {}).get("file_url")
				assets.append(url)
	for instructor in instructors:
		if instructor.get("user_image"):
			assets.append(instructor["user_image"])
	if len(evaluator):
		assets.append(evaluator[0].user_image)
	return assets


def read_asset_content(url):
	try:
		file_doc = frappe.get_doc("File", {"file_url": url})
		file_path = file_doc.get_full_path()
		with open(file_path, "rb") as f:
			return f.read()
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Could not read asset: {url}")
		return None


def create_course_zip(
	zip_filename,
	course,
	chapters,
	lessons,
	assets,
	assessments,
	questions,
	test_cases,
	instructors,
	evaluator,
):
	try:
		tmp_path = os.path.join(tempfile.gettempdir(), zip_filename)
		build_course_zip(
			tmp_path,
			course,
			chapters,
			lessons,
			assets,
			assessments,
			questions,
			test_cases,
			instructors,
			evaluator,
		)
		final_path = move_zip_to_public(tmp_path, zip_filename)
		schedule_file_deletion(final_path, delay_seconds=600)  # 10 minutes
		serve_zip(final_path, zip_filename)
	except Exception as e:
		print("Error creating ZIP file:", e)
		return None


def build_course_zip(
	tmp_path, course, chapters, lessons, assets, assessments, questions, test_cases, instructors, evaluator
):
	with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
		write_course_json(zip_file, course)
		write_chapters_json(zip_file, chapters)
		write_lessons_json(zip_file, lessons)
		write_assessments_json(zip_file, assessments, questions, test_cases)
		write_assets(zip_file, assets)
		write_instructors_json(zip_file, instructors)
		write_evaluator_json(zip_file, evaluator)


def write_course_json(zip_file, course):
	zip_file.writestr("course.json", frappe_json_dumps(course.as_dict()))


def write_chapters_json(zip_file, chapters):
	for chapter in chapters:
		chapter_data = chapter.as_dict()
		chapter_json = frappe_json_dumps(chapter_data)
		zip_file.writestr(f"chapters/{chapter.name}.json", chapter_json)


def write_lessons_json(zip_file, lessons):
	for lesson in lessons:
		lesson_data = lesson.as_dict()
		lesson_json = frappe_json_dumps(lesson_data)
		zip_file.writestr(f"lessons/{lesson.name}.json", lesson_json)


def write_assessments_json(zip_file, assessments, questions, test_cases):
	for question in questions:
		question_json = frappe_json_dumps(question)
		zip_file.writestr(f"assessments/questions/{question.name}.json", question_json)

	for test_case in test_cases:
		test_case_json = frappe_json_dumps(test_case)
		zip_file.writestr(f"assessments/test_cases/{test_case.name}.json", test_case_json)

	for assessment in assessments:
		assessment_json = frappe_json_dumps(assessment)
		zip_file.writestr(
			f"assessments/{assessment['doctype'].lower()}_{assessment['name']}.json", assessment_json
		)


def write_assets(zip_file, assets):
	assets = list(set(assets))
	for asset in assets:
		try:
			file_doc = frappe.get_doc("File", {"file_url": asset})
			file_path = os.path.abspath(file_doc.get_full_path())
			zip_file.write(file_path, f"assets/{os.path.basename(asset)}")
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Could not add asset: {asset}")
			continue


def move_zip_to_public(tmp_path, zip_filename):
	final_path = os.path.join(frappe.get_site_path("public", "files"), zip_filename)
	shutil.move(tmp_path, final_path)
	return final_path


def write_instructors_json(zip_file, instructors):
	instructors_json = frappe_json_dumps(instructors)
	zip_file.writestr("instructors.json", instructors_json)


def write_evaluator_json(zip_file, evaluator):
	if not len(evaluator):
		return
	evaluator_json = frappe_json_dumps(evaluator[0].as_dict())
	zip_file.writestr("evaluator.json", evaluator_json)


def serve_zip(final_path, zip_filename):
	with open(final_path, "rb") as f:
		frappe.local.response.filename = zip_filename
		frappe.local.response.filecontent = f.read()
		frappe.local.response.type = "download"
		frappe.local.response.content_type = "application/zip"


def schedule_file_deletion(file_path, delay_seconds=600):
	import threading

	def delete():
		try:
			if os.path.exists(file_path):
				os.remove(file_path)
		except Exception as e:
			frappe.log_error(f"Error deleting exported file {file_path}: {e}")

	timer = threading.Timer(delay_seconds, delete)
	timer.daemon = True
	timer.start()


def frappe_json_dumps(data):
	def default(obj):
		try:
			if isinstance(obj, (datetime | date | timedelta)):
				return str(obj)
		except Exception as e:
			frappe.log_error(f"Error serializing object {obj}: {e}")

	return json.dumps(data, indent=4, default=default)


def import_course_zip(zip_file_path):
	zip_file_path = zip_file_path.lstrip("/")
	actual_path = frappe.get_site_path(zip_file_path)
	with zipfile.ZipFile(actual_path, "r") as zip_file:
		course_data = read_json_from_zip(zip_file, "course.json")
		if not course_data:
			frappe.throw(_("Invalid course ZIP: Missing course.json"))

		create_assets(zip_file)
		create_user_for_instructors(zip_file)
		create_evaluator(zip_file)
		course_doc = create_course_doc(course_data)
		chapter_docs = create_chapter_docs(zip_file, course_doc.name)
		create_assessment_docs(zip_file)
		create_lesson_docs(zip_file, course_doc.name, chapter_docs)
		save_course_structure(zip_file, course_doc, chapter_docs)


def read_json_from_zip(zip_file, filename):
	try:
		with zip_file.open(filename) as f:
			return json.load(f)
	except Exception as e:
		frappe.log_error(f"Error reading {filename} from ZIP: {e}")
		return None


def create_user_for_instructors(zip_file):
	instructors = read_json_from_zip(zip_file, "instructors.json")
	if not instructors:
		return
	for instructor in instructors:
		if not frappe.db.exists("User", instructor["email"]):
			create_user(instructor)


def create_user(user):
	user_doc = frappe.new_doc("User")
	user_doc.email = user["email"]
	user_doc.first_name = user["first_name"] if user.get("first_name") else user["full_name"].split()[0]
	user_doc.last_name = (
		user["last_name"]
		if user.get("last_name")
		else " ".join(user["full_name"].split()[1:])
		if len(user["full_name"].split()) > 1
		else ""
	)
	user_doc.full_name = (
		user["full_name"] if user.get("full_name") else f"{user_doc.first_name} {user_doc.last_name}".strip()
	)
	user_doc.user_image = user.get("user_image")
	user_doc.insert(ignore_permissions=True)


def create_evaluator(zip_file):
	evaluator_data = read_json_from_zip(zip_file, "evaluator.json")
	if not evaluator_data:
		return
	if not frappe.db.exists("User", evaluator_data["evaluator"]):
		create_user(evaluator_data)

	if not frappe.db.exists("Course Evaluator", evaluator_data["name"]):
		evaluator_doc = frappe.new_doc("Course Evaluator")
		evaluator_doc.update(evaluator_data)
		evaluator_doc.insert(ignore_permissions=True)


def get_course_fields():
	return [
		"title",
		"tags",
		"image",
		"video_link",
		"card_gradient",
		"short_introduction",
		"description",
		"published",
		"upcoming",
		"featured",
		"disable_self_learning",
		"published_on",
		"category",
		"evaluator",
		"timezone",
		"paid_course",
		"paid_certificate",
		"course_price",
		"currency",
		"amount_usd",
		"enable_certification",
	]


def add_data_to_course(course_doc, course_data):
	for field in get_course_fields():
		if field in course_data:
			course_doc.set(field, course_data[field])


def add_instructors_to_course(course_doc, course_data):
	instructors = course_data.get("instructors", [])
	for instructor in instructors:
		course_doc.append("instructors", {"instructor": instructor["instructor"]})


def verify_category(category_name):
	if category_name and not frappe.db.exists("LMS Category", category_name):
		category = frappe.new_doc("LMS Category")
		category.category = category_name
		category.insert(ignore_permissions=True)


def create_course_doc(course_data):
	course_doc = frappe.new_doc("LMS Course")
	add_instructors_to_course(course_doc, course_data)
	verify_category(course_data.get("category"))
	course_data.pop("instructors", None)
	course_data.pop("chapters", None)
	add_data_to_course(course_doc, course_data)
	course_doc.insert(ignore_permissions=True)
	return course_doc


def create_chapter_docs(zip_file, course_name):
	chapter_docs = []
	for file in zip_file.namelist():
		if file.startswith("chapters/") and file.endswith(".json"):
			chapter_data = read_json_from_zip(zip_file, file)
			if chapter_data:
				chapter_doc = frappe.new_doc("Course Chapter")
				chapter_data.pop("lessons", None)
				chapter_doc.update(chapter_data)
				chapter_doc.course = course_name
				chapter_doc.insert(ignore_permissions=True)
				chapter_docs.append(chapter_doc)
	return chapter_docs


def get_chapter_name_for_lesson(zip_file, lesson_data, chapter_docs):
	for file in zip_file.namelist():
		if file.startswith("chapters/") and file.endswith(".json"):
			chapter_data = read_json_from_zip(zip_file, file)
			if chapter_data.get("name") == lesson_data.get("chapter"):
				title = chapter_data.get("title")
				chapter_doc = next((c for c in chapter_docs if c.title == title), None)
				if chapter_doc:
					return chapter_doc.name
	return None


def get_assessment_map():
	return {"quiz": "LMS Quiz", "assignment": "LMS Assignment", "program": "LMS Programming Exercise"}


def get_assessment_title(zip_file, assessment_name, assessment_type):
	assessment_map = get_assessment_map()
	file_name = f"assessments/{assessment_map.get(assessment_type, '').lower()}_{assessment_name}.json"
	try:
		with zip_file.open(file_name) as f:
			assessment_data = json.load(f)
			return assessment_data.get("title")
	except Exception as e:
		frappe.log_error(f"Error reading {file_name} from ZIP: {e}")
		return None


def replace_assessment_names(zip_file, content):
	assessment_types = ["quiz", "assignment", "program"]
	content = json.loads(content)
	for block in content.get("blocks", []):
		if block.get("type") in assessment_types:
			data_field = "exercise" if block.get("type") == "program" else block.get("type")
			assessment_name = block.get("data", {}).get(data_field)
			assessment_title = get_assessment_title(zip_file, assessment_name, block.get("type"))
			doctype = get_assessment_map().get(block.get("type"))
			current_assessment_name = frappe.db.get_value(doctype, {"title": assessment_title}, "name")
			if current_assessment_name:
				block["data"][data_field] = current_assessment_name
	return json.dumps(content)


def replace_assets(zip_file, content):
	content = json.loads(content)
	for block in content.get("blocks", []):
		if block.get("type") == "upload":
			asset_url = block.get("data", {}).get("file_url")
			if asset_url:
				asset_name = asset_url.split("/")[-1]
				current_asset_url = frappe.db.get_value("LMS Asset", {"file_name": asset_name}, "file_url")
				if current_asset_url:
					block["data"]["url"] = current_asset_url


def replace_values_in_content(zip_file, content):
	return replace_assessment_names(zip_file, content)
	# replace_assets(zip_file, content)


def create_lesson_docs(zip_file, course_name, chapter_docs):
	lesson_docs = []
	for file in zip_file.namelist():
		if file.startswith("lessons/") and file.endswith(".json"):
			lesson_data = read_json_from_zip(zip_file, file)
			if lesson_data:
				lesson_doc = frappe.new_doc("Course Lesson")
				lesson_doc.update(lesson_data)
				lesson_doc.course = course_name
				lesson_doc.chapter = get_chapter_name_for_lesson(zip_file, lesson_data, chapter_docs)
				lesson_doc.content = (
					replace_values_in_content(zip_file, lesson_doc.content) if lesson_doc.content else None
				)
				lesson_doc.insert(ignore_permissions=True)
				lesson_docs.append(lesson_doc)
	return lesson_docs


def create_question_doc(zip_file, file):
	question_data = read_json_from_zip(zip_file, file)
	if question_data:
		doc = frappe.new_doc("LMS Question")
		doc.update(question_data)
		doc.insert(ignore_permissions=True)


def create_test_case_doc(zip_file, file):
	test_case_data = read_json_from_zip(zip_file, file)
	if test_case_data:
		doc = frappe.new_doc("LMS Test Case")
		doc.update(test_case_data)
		doc.insert(ignore_permissions=True)


def add_questions_to_quiz(quiz_doc, questions):
	for question in questions:
		question_detail = question["question_detail"]
		question_name = frappe.db.get_value("LMS Question", {"question": question_detail}, "name")
		if question_name:
			quiz_doc.append("questions", {"question": question_name})


def create_assessment_docs(zip_file):
	for file in zip_file.namelist():
		if file.startswith("assessments/questions/") and file.endswith(".json"):
			create_question_doc(zip_file, file)
		elif file.startswith("assessments/test_cases/") and file.endswith(".json"):
			create_test_case_doc(zip_file, file)

	for file in zip_file.namelist():
		if (
			file.startswith("assessments/")
			and file.endswith(".json")
			and not file.startswith("assessments/questions/")
			and not file.startswith("assessments/test_cases/")
		):
			assessment_data = read_json_from_zip(zip_file, file)
			if not assessment_data:
				continue
			assessment_data.pop("lesson", None)
			assessment_data.pop("course", None)
			doctype = assessment_data.get("doctype")
			if doctype in ("LMS Quiz", "LMS Assignment", "LMS Programming Exercise") and not frappe.db.exists(
				doctype, assessment_data.get("name")
			):
				questions = assessment_data.pop("questions", [])
				test_cases = assessment_data.pop("test_cases", [])
				doc = frappe.new_doc(doctype)
				doc.update(assessment_data)
				if doctype == "LMS Quiz":
					add_questions_to_quiz(doc, questions)
				elif doctype == "LMS Programming Exercise":
					for row in test_cases:
						doc.append(
							"test_cases", {"input": row["input"], "expected_output": row["expected_output"]}
						)
				doc.insert(ignore_permissions=True)


def create_assets(zip_file):
	for file in zip_file.namelist():
		if file.startswith("assets/") and not file.endswith("/"):
			try:
				with zip_file.open(file) as f:
					content = f.read()
					asset_name = file.split("/")[-1]
					if not frappe.db.exists("File", {"file_name": asset_name}):
						asset_doc = frappe.new_doc("File")
						asset_doc.file_name = asset_name
						asset_doc.content = content
						asset_doc.insert(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(f"Error processing asset {file}: {e}")


def get_lesson_title(zip_file, lesson_name):
	for file in zip_file.namelist():
		if file.startswith("lessons/") and file.endswith(".json"):
			lesson_data = read_json_from_zip(zip_file, file)
			if lesson_data.get("name") == lesson_name:
				return lesson_data.get("title")
	return None


def add_lessons_to_chapters(zip_file, course_name, chapter_docs):
	for file in zip_file.namelist():
		if file.startswith("chapters/") and file.endswith(".json"):
			chapter_data = read_json_from_zip(zip_file, file)
			chapter_doc = next((c for c in chapter_docs if c.title == chapter_data.get("title")), None)
			if not chapter_doc:
				continue
			for lesson in chapter_data.get("lessons", []):
				lesson_title = get_lesson_title(zip_file, lesson["lesson"])
				lesson_name = frappe.db.get_value(
					"Course Lesson", {"title": lesson_title, "course": course_name}, "name"
				)
				if lesson_name:
					chapter_doc.append("lessons", {"lesson": lesson_name})
			chapter_doc.save(ignore_permissions=True)


def add_chapter_to_course(course_doc, chapter_docs):
	course_doc.reload()
	for chapter_doc in chapter_docs:
		course_doc.append("chapters", {"chapter": chapter_doc.name})
	course_doc.save(ignore_permissions=True)


def save_course_structure(zip_file, course_doc, chapter_docs):
	add_chapter_to_course(course_doc, chapter_docs)
	add_lessons_to_chapters(zip_file, course_doc.name, chapter_docs)

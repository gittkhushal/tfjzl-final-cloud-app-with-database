from django.shortcuts import render
from django.http import HttpResponseRedirect
from .models import Course, Enrollment, Lesson, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}
    if request.method == 'POST':
        username = request.POST['username']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        password = request.POST['psw']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except Exception:
            logger.error("Failed to find user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name, password=password)
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "User already exists"
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password"
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.is_authenticated:
        if Enrollment.objects.filter(user=user, course=course).exists():
            is_enrolled = True
    return is_enrolled


# Course list view
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        return Course.objects.order_by('-total_enrollment')[:10]


# Course detail view
class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        user = self.request.user
        context['is_enrolled'] = check_if_enrolled(user, course)
        return context


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if not user.is_authenticated:
        return redirect('onlinecourse:login')

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled:
        Enrollment.objects.create(user=user, course=course, mode='audit')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))


# Helper method to collect selected choices from exam form
def extract_answers(request):
    submitted_answers = []
    for key in request.POST:
        if key.startswith('choice_'):
            value = request.POST[key]
            choice_id = int(value)
            submitted_answers.append(choice_id)
        elif key.startswith('choice'):
            value = request.POST[key]
            choice_id = int(value)
            submitted_answers.append(choice_id)
    return submitted_answers


# Submit view to create an exam submission record
def submit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if not user.is_authenticated:
        return redirect('onlinecourse:login')

    enrollment = Enrollment.objects.get(user=user, course=course)
    submission = Submission.objects.create(enrollment=enrollment)

    selected_choice_ids = extract_answers(request)
    for choice_id in selected_choice_ids:
        choice = Choice.objects.get(pk=choice_id)
        submission.choices.add(choice)

    return HttpResponseRedirect(reverse('onlinecourse:show_exam_result', args=(course.id, submission.id)))


# Exam result view to check if learner passed exam and show question results
def show_exam_result(request, course_id, submission_id):
    context = {}
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)
    choices = submission.choices.all()
    selected_ids = [choice.id for choice in choices]

    questions = course.question_set.all()
    total_score = 0
    possible = 0
    for question in questions:
        possible += question.grade
        if question.is_get_score(selected_ids):
            total_score += question.grade

    context['course'] = course
    context['submission'] = submission
    context['grade'] = total_score
    context['possible'] = possible
    context['selected_ids'] = selected_ids
    return render(request, 'onlinecourse/exam_result_bootstrap.html', context)

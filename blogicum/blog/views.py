from django.core.cache import cache
from django.http import Http404, HttpResponseForbidden
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)

from blog.forms import CommentEditForm, PostEditForm, UserEditForm
from blog.models import Category, Post, User, Comment
from blog.mixins import ProfileSuccessUrlMixin, CommonPostMixin, CommentMixin
from django.contrib.auth.mixins import LoginRequiredMixin


def create_queryset(manager=Post.objects, filters=True, annotations=True):
    queryset = manager.select_related(
        'author',
        'location',
        'category'
    )
    if filters:
        queryset = queryset.filter(
            pub_date__lt=timezone.now(),
            is_published=True,
            category__is_published=True,
        )
    if annotations:
        queryset = queryset.annotate(
            comment_count=Count('comments')
        ).order_by('-pub_date')
    return queryset


class IndexListView(ListView):
    queryset = create_queryset()
    template_name = 'blog/index.html'
    ordering = '-pub_date'
    paginate_by = settings.MAX_POST_ON_PAGE


class CategoryListView(IndexListView):
    template_name = 'blog/category.html'

    def get_queryset(self):
        category_slug = self.kwargs.get('category_slug')
        self.category = get_object_or_404(
            Category,
            slug=category_slug,
            is_published=True
        )
        return create_queryset(manager=self.category.posts)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context


class ProfileListView(IndexListView, ListView):
    template_name = 'blog/profile.html'

    def get_queryset(self):
        self.author = get_object_or_404(
            User,
            username=self.kwargs.get('username')
        )
        if self.request.user != self.author:
            queryset = create_queryset(
                manager=self.author.posts,
                filters=True,
                annotations=True
            )
        else:
            queryset = create_queryset(
                manager=self.author.posts,
                filters=False,
                annotations=True
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.author
        return context


@login_required
def add_comment(request, post_id):
    comment = get_object_or_404(Post, pk=post_id)
    form = CommentEditForm(request.POST)
    if form.is_valid():
        commentary = form.save(commit=False)
        commentary.author = request.user
        commentary.post = comment
        commentary.save()
    return redirect('blog:post_detail', post_id=post_id)


class PostCreateView(LoginRequiredMixin, ProfileSuccessUrlMixin, CreateView):
    model = Post
    form_class = PostEditForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostDetailView(DetailView):
    model = Post
    pk_url_kwarg = 'post_id'
    template_name = 'blog/detail.html'
    paginate_by = settings.MAX_POST_ON_PAGE

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CommentEditForm()
        context['comments'] = (
            self.object.comments.all().select_related('author')
        )
        return context

    def get_object(self, queryset=None):
        post = super().get_object(queryset=queryset)
        if (post.author != self.request.user
                and (not post.is_published
                     or not post.category.is_published
                     or post.pub_date > timezone.now())):
            raise Http404()
        return post


class ProfileUpdateView(
    LoginRequiredMixin, ProfileSuccessUrlMixin, UpdateView
):
    form_class = UserEditForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user


class PostUpdateView(CommonPostMixin, UpdateView):
    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.pk}
        )


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    pk_url_kwarg = 'post_id'
    template_name = 'blog/create.html'
    success_url = reverse_lazy('blog:index')
    # Оставила reverse_lazy т.к. на уровне класса, с reverse не проходят тесты

    def dispatch(self, request, *args, **kwargs):
        """Проверка прав доступа перед выполнением"""
        self.object = self.get_object()
        if self.object.author != request.user:
            return HttpResponseForbidden(
                'У вас нет прав на удаление этого поста'
            )
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """Кастомная логика удаления с очисткой зависимостей"""
        post = self.get_object()
        post.comments.all().delete()
        cache.clear()
        return super().delete(request, *args, **kwargs)


class CommentUpdateView(CommentMixin, UpdateView):
    pass


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    pk_url_kwarg = 'comment_id'
    template_name = 'blog/comment.html'

    def dispatch(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if comment.author != request.user:
            return HttpResponseForbidden(
                'У вас нет прав на удаление этого комментария'
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Удаляем ненужную форму из контекста."""
        context = super().get_context_data(**kwargs)
        if 'form' in context:
            del context["form"]
        return context

    def get_success_url(self):
        """URL для перенаправления после удаления."""
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.kwargs['post_id']}
        )

    def delete(self, request, *args, **kwargs):
        """Обработка удаления комментария."""
        comment = self.get_object()
        comment.delete()
        return redirect(self.get_success_url())


class ProfileCreateView(CreateView):
    form_class = UserEditForm
    template_name = 'registration/registration_form.html'
    success_url = reverse_lazy('login')
    # Оставила reverse_lazy т.к. на уровне класса, с reverse не проходят тесты

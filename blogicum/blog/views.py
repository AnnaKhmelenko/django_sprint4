from django.http import HttpResponseForbidden
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)

from blog.forms import CommentEditForm, PostEditForm, UserEditForm
from blog.models import Category, Comment, Post, User


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


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostEditForm
    template_name = 'blog/create.html'

    def get_success_url(self):
        return reverse_lazy(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )

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
        context['form'] = CommentEditForm(instance=self.object)
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


class ProfiletUpdateView(LoginRequiredMixin, UpdateView):
    form_class = UserEditForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class CommonPostMixin:
    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'
    form_class = PostEditForm
    posts = None

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs.get('post_id'))
        if post.author != request.user:
            return redirect('blog:post_detail', self.kwargs.get('post_id'))
        return super().dispatch(request, *args, **kwargs)


class PostUpdateView(CommonPostMixin, LoginRequiredMixin, UpdateView):
    def get_success_url(self):
        return reverse_lazy(
            'blog:post_detail',
            kwargs={'post_id': self.object.pk}
        )


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    pk_url_kwarg = 'post_id'
    template_name = 'blog/create.html'
    success_url = reverse_lazy('blog:index')

    def dispatch(self, request, *args, **kwargs):
        """Проверка прав доступа перед выполнением"""
        self.object = self.get_object()
        if self.object.author != request.user:
            return HttpResponseForbidden(
                "У вас нет прав на удаление этого поста"
            )
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """Кастомная логика удаления с очисткой зависимостей"""
        from django.core.cache import cache
        # Получаем пост и его ID до удаления
        post = self.get_object()
        post_id = post.id
        # Удаляем все связанные комментарии
        post.comments.all().delete()
        # Очищаем кэш
        cache.clear()
        # Выполняем стандартное удаление
        response = super().delete(request, *args, **kwargs)
        # Дополнительная проверка, что пост действительно удален
        if Post.objects.filter(id=post_id).exists():
            raise Exception(
                f"Пост с ID {post_id} не был удален из базы данных!"
            )
        return response


class CommentMixin:
    model = Comment
    form_class = CommentEditForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'
    comment = None

    def dispatch(self, request, *args, **kwargs):
        comment_id = kwargs.get('comment_id')
        if not comment_id:
            raise Http404("comment_id not provided")
        instance = get_object_or_404(Comment, pk=comment_id)
        if instance.author != request.user:
            return redirect('blog:post_detail', post_id=instance.post.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.comment = self.comment
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            'blog:post_detail',
            kwargs={'post_id': self.kwargs.get('post_id')}
        )


class CommentUpdateView(LoginRequiredMixin, CommentMixin, UpdateView):
    pass


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    pk_url_kwarg = 'comment_id'
    template_name = 'blog/comment.html'

    def dispatch(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if comment.author != request.user:
            return HttpResponseForbidden(
                "У вас нет прав на удаление этого комментария"
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'form' in context:
            del context['form']
        return context

    def get_success_url(self):
        return reverse_lazy(
            'blog:post_detail',
            kwargs={'post_id': self.kwargs['post_id']}
        )


class ProfileCreateView(CreateView):
    form_class = UserEditForm
    template_name = 'registration/registration_form.html'
    success_url = reverse_lazy('login')

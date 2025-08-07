from django.urls import reverse
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin

from blog.models import Post, Comment
from blog.forms import PostEditForm, CommentEditForm


class ProfileSuccessUrlMixin:
    """Миксин для URL перенаправления после успешного действия в профиле"""

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class CommonPostMixin(LoginRequiredMixin):
    """Общий миксин для работы с постами"""

    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'
    form_class = PostEditForm

    def dispatch(self, request, *args, **kwargs):
        """Проверка прав доступа перед выполнением"""
        post = get_object_or_404(Post, pk=kwargs.get('post_id'))
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=post.pk)
        return super().dispatch(request, *args, **kwargs)


class CommentMixin(LoginRequiredMixin):
    """Базовый миксин для работы с комментариями"""

    model = Comment
    form_class = CommentEditForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def dispatch(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs.get('comment_id'))
        if comment.author != request.user:
            return redirect('blog:post_detail', post_id=comment.post.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.kwargs.get('post_id')}
        )

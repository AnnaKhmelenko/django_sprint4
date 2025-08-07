from django import forms

from blog.models import Comment, Post, User


class CommentEditForm(forms.ModelForm):

    class Meta:
        model = Comment
        fields = ('text',)


class PostEditForm(forms.ModelForm):

    class Meta:
        model = Post
        exclude = ('author',)
        widgets = {
            'text': forms.Textarea(),
            'comment': forms.Textarea(),
            'pub_date': forms.DateTimeInput(
                format='%Y-%m-%d %H:%M:%S',
                attrs={'type': 'datetime-local'}),
        }


class UserEditForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')

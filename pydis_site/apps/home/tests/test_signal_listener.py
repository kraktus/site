from unittest import mock

from allauth.account.signals import user_logged_in
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.socialaccount.providers.discord.provider import DiscordProvider
from allauth.socialaccount.providers.github.provider import GitHubProvider
from allauth.socialaccount.signals import (
    pre_social_login, social_account_added, social_account_removed,
    social_account_updated)
from django.contrib.auth.models import Group, User as DjangoUser
from django.db.models.signals import post_save
from django.test import TestCase

from pydis_site.apps.api.models import Role, User as DiscordUser
from pydis_site.apps.home.signals import SignalListener
from pydis_site.apps.staff.models import RoleMapping


class SignalListenerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Executed when testing begins."""
        cls.admin_role = Role.objects.create(
            id=0,
            name="admin",
            colour=0,
            permissions=0,
            position=0
        )

        cls.admin_group = Group.objects.create(name="admin")

        cls.role_mapping = RoleMapping.objects.create(
            role=cls.admin_role,
            group=cls.admin_group
        )

        cls.unmapped_role = Role.objects.create(
            id=1,
            name="unmapped",
            colour=0,
            permissions=0,
            position=1
        )

        cls.discord_user = DiscordUser.objects.create(
            id=0,
            name="user",
            discriminator=0,
            avatar_hash=None
        )

        cls.discord_unmapped = DiscordUser.objects.create(
            id=2,
            name="unmapped",
            discriminator=0,
            avatar_hash=None
        )

        cls.discord_unmapped.roles.add(cls.unmapped_role)
        cls.discord_unmapped.save()

        cls.discord_not_in_guild = DiscordUser.objects.create(
            id=3,
            name="not-in-guild",
            discriminator=0,
            avatar_hash=None,
            in_guild=False
        )

        cls.discord_admin = DiscordUser.objects.create(
            id=1,
            name="admin",
            discriminator=0,
            avatar_hash=None
        )

        cls.discord_admin.roles.set([cls.admin_role])
        cls.discord_admin.save()

        cls.django_user_discordless = DjangoUser.objects.create(username="no-discord")
        cls.django_user_never_joined = DjangoUser.objects.create(username="never-joined")

        cls.social_never_joined = SocialAccount.objects.create(
            user=cls.django_user_never_joined,
            provider=DiscordProvider.id,
            uid=5
        )

        cls.django_user = DjangoUser.objects.create(username="user")

        cls.social_user = SocialAccount.objects.create(
            user=cls.django_user,
            provider=DiscordProvider.id,
            uid=cls.discord_user.id
        )

        cls.social_user_github = SocialAccount.objects.create(
            user=cls.django_user,
            provider=GitHubProvider.id,
            uid=cls.discord_user.id
        )

        cls.social_unmapped = SocialAccount(
            # We instantiate it and don't put it in the DB. This is (surprisingly)
            # a realistic test case, so we need to check for it

            provider=DiscordProvider.id,
            uid=5,
            user_id=None  # No relation exists at all
        )

        cls.django_admin = DjangoUser.objects.create(
            username="admin",
            is_staff=True,
            is_superuser=True
        )

        cls.social_admin = SocialAccount.objects.create(
            user=cls.django_admin,
            provider=DiscordProvider.id,
            uid=cls.discord_admin.id
        )

    def test_model_save(self):
        """Test signal handling for when Discord user model objects are saved to DB."""
        mock_obj = mock.Mock()

        with mock.patch.object(SignalListener, "_apply_groups", mock_obj):
            _ = SignalListener()

            post_save.send(
                DiscordUser,
                instance=self.discord_user,
                raw=True,
                created=None,  # Not realistic, but we don't use it
                using=None,  # Again, we don't use it
                update_fields=False  # Always false during integration testing
            )

            mock_obj.assert_not_called()

            post_save.send(
                DiscordUser,
                instance=self.discord_user,
                raw=False,
                created=None,  # Not realistic, but we don't use it
                using=None,  # Again, we don't use it
                update_fields=False  # Always false during integration testing
            )

            mock_obj.assert_called_with(self.discord_user, self.social_user)

    def test_pre_social_login(self):
        """Test the pre-social-login Allauth signal handling."""
        mock_obj = mock.Mock()

        discord_login = SocialLogin(self.django_user, self.social_user)
        github_login = SocialLogin(self.django_user, self.social_user_github)
        unmapped_login = SocialLogin(self.django_user, self.social_unmapped)

        with mock.patch.object(SignalListener, "_apply_groups", mock_obj):
            _ = SignalListener()

            # Don't attempt to apply groups if the user doesn't have a linked Discord account
            pre_social_login.send(SocialLogin, sociallogin=github_login)
            mock_obj.assert_not_called()

            # Don't attempt to apply groups if the user hasn't joined the Discord server
            pre_social_login.send(SocialLogin, sociallogin=unmapped_login)
            mock_obj.assert_not_called()

            # Attempt to apply groups if everything checks out
            pre_social_login.send(SocialLogin, sociallogin=discord_login)
            mock_obj.assert_called_with(self.discord_user, self.social_user)

    def test_social_added(self):
        """Test the social-account-added Allauth signal handling."""
        mock_obj = mock.Mock()

        discord_login = SocialLogin(self.django_user, self.social_user)
        github_login = SocialLogin(self.django_user, self.social_user_github)
        unmapped_login = SocialLogin(self.django_user, self.social_unmapped)

        with mock.patch.object(SignalListener, "_apply_groups", mock_obj):
            _ = SignalListener()

            # Don't attempt to apply groups if the user doesn't have a linked Discord account
            social_account_added.send(SocialLogin, sociallogin=github_login)
            mock_obj.assert_not_called()

            # Don't attempt to apply groups if the user hasn't joined the Discord server
            social_account_added.send(SocialLogin, sociallogin=unmapped_login)
            mock_obj.assert_not_called()

            # Attempt to apply groups if everything checks out
            social_account_added.send(SocialLogin, sociallogin=discord_login)
            mock_obj.assert_called_with(self.discord_user, self.social_user)

    def test_social_updated(self):
        """Test the social-account-updated Allauth signal handling."""
        mock_obj = mock.Mock()

        discord_login = SocialLogin(self.django_user, self.social_user)
        github_login = SocialLogin(self.django_user, self.social_user_github)
        unmapped_login = SocialLogin(self.django_user, self.social_unmapped)

        with mock.patch.object(SignalListener, "_apply_groups", mock_obj):
            _ = SignalListener()

            # Don't attempt to apply groups if the user doesn't have a linked Discord account
            social_account_updated.send(SocialLogin, sociallogin=github_login)
            mock_obj.assert_not_called()

            # Don't attempt to apply groups if the user hasn't joined the Discord server
            social_account_updated.send(SocialLogin, sociallogin=unmapped_login)
            mock_obj.assert_not_called()

            # Attempt to apply groups if everything checks out
            social_account_updated.send(SocialLogin, sociallogin=discord_login)
            mock_obj.assert_called_with(self.discord_user, self.social_user)

    def test_social_removed(self):
        """Test the social-account-removed Allauth signal handling."""
        mock_obj = mock.Mock()

        with mock.patch.object(SignalListener, "_apply_groups", mock_obj):
            _ = SignalListener()

            # Don't attempt to remove groups if the user doesn't have a linked Discord account
            social_account_removed.send(SocialLogin, socialaccount=self.social_user_github)
            mock_obj.assert_not_called()

            # Don't attempt to remove groups if the social account doesn't map to a Django user
            social_account_removed.send(SocialLogin, socialaccount=self.social_unmapped)
            mock_obj.assert_not_called()

            # Attempt to remove groups if everything checks out
            social_account_removed.send(SocialLogin, socialaccount=self.social_user)
            mock_obj.assert_called_with(self.discord_user, self.social_user, True)

    def test_logged_in(self):
        """Test the user-logged-in Allauth signal handling."""
        mock_obj = mock.Mock()

        with mock.patch.object(SignalListener, "_apply_groups", mock_obj):
            _ = SignalListener()

            # Don't attempt to apply groups if the user doesn't have a linked Discord account
            user_logged_in.send(DjangoUser, user=self.django_user_discordless)
            mock_obj.assert_not_called()

            # Don't attempt to apply groups if the user hasn't joined the Discord server
            user_logged_in.send(DjangoUser, user=self.django_user_never_joined)
            mock_obj.assert_not_called()

            # Attempt to apply groups if everything checks out
            user_logged_in.send(DjangoUser, user=self.django_user)
            mock_obj.assert_called_with(self.discord_user, self.social_user)

    def test_apply_groups_admin(self):
        """Test application of groups by role, relating to an admin user."""
        handler = SignalListener()

        self.assertTrue(self.django_user_discordless.groups.all().count() == 0)

        # Apply groups based on admin role being present on Discord
        handler._apply_groups(self.discord_admin, self.social_admin)
        self.assertTrue(self.admin_group in self.django_admin.groups.all())

        # Remove groups based on the user apparently leaving the server
        handler._apply_groups(self.discord_admin, self.social_admin, True)
        self.assertTrue(self.django_user_discordless.groups.all().count() == 0)

        # Apply the admin role again
        handler._apply_groups(self.discord_admin, self.social_admin)

        # Remove all of the roles from the user
        self.discord_admin.roles.clear()

        # Remove groups based on the user no longer having the admin role on Discord
        handler._apply_groups(self.discord_admin, self.social_admin)
        self.assertTrue(self.django_user_discordless.groups.all().count() == 0)

        self.discord_admin.roles.add(self.admin_role)
        self.discord_admin.save()

    def test_apply_groups_other(self):
        """Test application of groups by role, relating to non-standard cases."""
        handler = SignalListener()

        self.assertTrue(self.django_user_discordless.groups.all().count() == 0)

        # No groups should be applied when there's no user account yet
        handler._apply_groups(self.discord_unmapped, self.social_unmapped)
        self.assertTrue(self.django_user_discordless.groups.all().count() == 0)

        # No groups should be applied when there are only unmapped roles to match
        handler._apply_groups(self.discord_unmapped, self.social_user)
        self.assertTrue(self.django_user.groups.all().count() == 0)

        # No groups should be applied when the user isn't in the guild
        handler._apply_groups(self.discord_not_in_guild, self.social_user)
        self.assertTrue(self.django_user.groups.all().count() == 0)

    def test_role_mapping_str(self):
        """Test that role mappings stringify correctly."""
        self.assertTrue(
            str(self.role_mapping) == f"@{self.admin_role.name} -> {self.admin_group.name}"
        )
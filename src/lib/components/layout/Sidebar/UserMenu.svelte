<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { createEventDispatcher, getContext, onMount, tick } from 'svelte';

	import { goto } from '$app/navigation';
	import { fade, slide } from 'svelte/transition';

	import { getUsage } from '$lib/apis';
	import { getSessionUser, userSignOut } from '$lib/apis/auths';

	import { showSettings, mobile, showSidebar, showShortcuts, user, config } from '$lib/stores';

	import { ARKIVE_API_BASE_URL } from '$lib/constants';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import Keyboard from '$lib/components/icons/Keyboard.svelte';
	import ShortcutsModal from '$lib/components/chat/ShortcutsModal.svelte';
	import Settings from '$lib/components/icons/Settings.svelte';
	import UserGroup from '$lib/components/icons/UserGroup.svelte';
	import SignOut from '$lib/components/icons/SignOut.svelte';
	import FaceSmile from '$lib/components/icons/FaceSmile.svelte';
	import UserStatusModal from './UserStatusModal.svelte';
	import Emoji from '$lib/components/common/Emoji.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { updateUserStatus } from '$lib/apis/users';
	import { toast } from 'svelte-sonner';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let show = false;
	export let role = '';

	export let profile = false;
	export let help = false;

	export let className = 'w-[240px]';
	export let align = 'end';

	export let showActiveUsers = true;

	let showUserStatusModal = false;

	const dispatch = createEventDispatcher();

	let usage = null;
	const getUsageInfo = async () => {
		const res = await getUsage(localStorage.token).catch((error) => {
			console.error('Error fetching usage info:', error);
		});

		if (res) {
			usage = res;
		} else {
			usage = null;
		}
	};

	const handleDropdownChange = (state) => {
		dispatch('change', state);

		// Fetch usage info when dropdown opens, if user has permission
		if (state && ($config?.features?.enable_public_active_users_count || role === 'admin')) {
			getUsageInfo();
		}
	};
</script>

<ShortcutsModal bind:show={$showShortcuts} />
<UserStatusModal
	bind:show={showUserStatusModal}
	onSave={async () => {
		user.set(await getSessionUser(localStorage.token));
	}}
/>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<Dropdown bind:show onOpenChange={handleDropdownChange} {align}>
	<slot />

	<div slot="content">
		<div
			class="{className} z-50 rounded-2xl border border-gray-200 bg-white/95 p-1.5 text-sm text-gray-900 shadow-2xl shadow-black/10 backdrop-blur-xl dark:border-white/[0.08] dark:bg-[#080a10]/95 dark:text-white dark:shadow-black/40"
		>
			{#if profile}
				<div class="flex w-full items-center gap-3 rounded-xl p-2.5">
					<div class="flex shrink-0 items-center">
						<img
							src={`${ARKIVE_API_BASE_URL}/users/${$user?.id}/profile/image`}
							class="size-10 rounded-full object-cover ring-1 ring-black/5 dark:ring-white/10"
							alt="profile"
						/>
					</div>

					<div class="flex w-full flex-1 flex-col overflow-hidden">
						<div class="font-medium line-clamp-1 pr-2">
							{$user.name}
						</div>

						<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
							{#if $user?.is_active ?? true}
								<div>
									<span class="relative flex size-2">
										<span class="relative inline-flex rounded-full size-2 bg-green-500" ></span>
									</span>
								</div>

								<span class="text-xs"> {$i18n.t('Active')} </span>
							{:else}
								<div>
									<span class="relative flex size-2">
										<span class="relative inline-flex rounded-full size-2 bg-gray-500" ></span>
									</span>
								</div>

								<span class="text-xs"> {$i18n.t('Away')} </span>
							{/if}
						</div>
					</div>
				</div>

				{#if $user?.status_emoji || $user?.status_message}
					<div class="mx-1">
						<button
							class="mb-1 flex w-full items-center gap-2 rounded-xl bg-gray-50 px-2.5 py-2 text-left text-xs text-gray-900 transition hover:bg-gray-100 dark:bg-white/[0.045] dark:text-white dark:hover:bg-white/[0.07]"
							type="button"
							on:click={() => {
								show = false;
								showUserStatusModal = true;
							}}
						>
							{#if $user?.status_emoji}
								<div class=" self-center shrink-0">
									<Emoji className="size-4" shortCode={$user?.status_emoji} />
								</div>
							{/if}

							<Tooltip
								content={$user?.status_message}
								className=" self-center line-clamp-2 flex-1 text-left"
							>
								{$user?.status_message}
							</Tooltip>

							<div class="self-start">
								<Tooltip content={$i18n.t('Clear status')}>
									<button
										type="button"
										on:click={async (e) => {
											e.preventDefault();
											e.stopPropagation();
											e.stopImmediatePropagation();

											const res = await updateUserStatus(localStorage.token, {
												status_emoji: '',
												status_message: ''
											});

											if (res) {
												toast.success($i18n.t('Status cleared successfully'));
												user.set(await getSessionUser(localStorage.token));
											} else {
												toast.error($i18n.t('Failed to clear status'));
											}
										}}
									>
										<XMark className="size-4 opacity-50" strokeWidth="2" />
									</button>
								</Tooltip>
							</div>
						</button>
					</div>
				{:else}
					<div class="mx-1">
						<button
							class="mb-1 flex w-full items-center justify-center gap-1 rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-900 transition hover:bg-gray-100 dark:bg-white/[0.045] dark:text-white dark:hover:bg-white/[0.07]"
							type="button"
							on:click={() => {
								show = false;
								showUserStatusModal = true;
							}}
						>
							<div class=" self-center">
								<FaceSmile className="size-4" strokeWidth="1.5" />
							</div>
							<div class=" self-center truncate">{$i18n.t('Update your status')}</div>
						</button>
					</div>
				{/if}

				<hr class="my-1.5 border-gray-100 p-0 dark:border-white/[0.06]" />
			{/if}

			<button
				class="flex h-10 w-full cursor-pointer select-none items-center rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				type="button"
				on:click={async () => {
					show = false;

					await showSettings.set(true);

					if ($mobile) {
						await tick();
						showSidebar.set(false);
					}
				}}
			>
				<div class="mr-3 flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
					<Settings className="w-5 h-5" strokeWidth="1.5" />
				</div>
				<div class="truncate font-medium">{$i18n.t('Settings')}</div>
			</button>

			<button
				class="flex h-10 w-full cursor-pointer select-none items-center rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				type="button"
				on:click={async () => {
					show = false;

					dispatch('show', 'archived-chat');

					if ($mobile) {
						await tick();

						showSidebar.set(false);
					}
				}}
			>
				<div class="mr-3 flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
					<ArchiveBox className="size-5" strokeWidth="1.5" />
				</div>
				<div class="truncate font-medium">{$i18n.t('Archived Chats')}</div>
			</button>

			{#if role === 'admin'}
				<a
					href="/admin"
					draggable="false"
					class="flex h-10 w-full cursor-pointer select-none items-center rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
					on:click={async (e) => {
						if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) {
							return;
						}
						e.preventDefault();
						show = false;
						goto('/admin');
						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class="mr-3 flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
						<UserGroup className="w-5 h-5" strokeWidth="1.5" />
					</div>
					<div class="truncate font-medium">{$i18n.t('Admin Panel')}</div>
				</a>
			{/if}

			{#if help}
				<hr class="my-1 border-gray-100 p-0 dark:border-white/[0.06]" />

				<!-- {$i18n.t('Help')} -->

				<button
					class="flex h-10 w-full cursor-pointer select-none items-center rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
					type="button"
					id="chat-share-button"
					on:click={async () => {
						show = false;
						showShortcuts.set(!$showShortcuts);

						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class="mr-3 flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
						<Keyboard className="size-5" />
					</div>
					<div class="truncate font-medium">{$i18n.t('Keyboard shortcuts')}</div>
				</button>
			{/if}

			<hr class="my-1 border-gray-100 p-0 dark:border-white/[0.06]" />

			<button
				class="flex h-10 w-full cursor-pointer select-none items-center rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				type="button"
				on:click={async () => {
					const res = await userSignOut();
					user.set(null);
					localStorage.removeItem('token');

					location.href = res?.redirect_url ?? '/auth';
					show = false;
				}}
			>
				<div class="mr-3 flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
					<SignOut className="w-5 h-5" strokeWidth="1.5" />
				</div>
				<div class="truncate font-medium">{$i18n.t('Sign Out')}</div>
			</button>

			{#if showActiveUsers && ($config?.features?.enable_public_active_users_count || role === 'admin') && usage}
				{#if usage?.user_count}
					<hr class="my-1 border-gray-100 p-0 dark:border-white/[0.06]" />

					<Tooltip
						content={usage?.model_ids && usage?.model_ids.length > 0
							? `${$i18n.t('Running')}: ${usage.model_ids.join(', ')} ✨`
							: ''}
					>
						<div
							class="flex items-center gap-2.5 rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-700 dark:bg-white/[0.035] dark:text-gray-300"
							on:mouseenter={() => {
								if ($config?.features?.enable_public_active_users_count || role === 'admin') {
									getUsageInfo();
								}
							}}
						>
							<div class=" flex items-center">
								<span class="relative flex size-2">
									<span class="relative inline-flex rounded-full size-2 bg-green-500" ></span>
								</span>
							</div>

							<div class=" ">
								<span class="">
									{$i18n.t('Active Users')}:
								</span>
								<span class=" font-semibold">
									{usage?.user_count}
								</span>
							</div>
						</div>
					</Tooltip>
				{/if}
			{/if}
		</div>
	</div>
</Dropdown>

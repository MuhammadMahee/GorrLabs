<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';

	import { ARKIVE_NAME, config, mobile, showSidebar, user } from '$lib/stores';
	import { page } from '$app/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import Sidebar from '$lib/components/icons/Sidebar.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Admin Panel')} • {$ARKIVE_NAME}
	</title>
</svelte:head>

{#if loaded}
	<div
		class="arkive-page flex flex-col h-screen max-h-[100dvh] flex-1 transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-var(--sidebar-width))]'
			: ' md:max-w-[calc(100%-49px)]'}  w-full max-w-full"
	>
		<nav class="arkive-topbar px-2.5 pt-1.5 drag-region select-none">
			<div class=" flex items-center gap-1">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-end">
						<Tooltip
							content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							interactive={true}
						>
							<button
								id="sidebar-toggle-button"
								class=" cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-"
								on:click={() => {
									showSidebar.set(!$showSidebar);
								}}
							>
								<div class=" self-center p-1.5">
									<Sidebar />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div class=" flex w-full">
					<div
						class="flex gap-1 scrollbar-none overflow-x-auto w-fit text-center text-sm font-medium rounded-full bg-transparent pt-1"
					>
						<a
							draggable="false"
							aria-current={$page.url.pathname === '/admin' ||
							$page.url.pathname.includes('/admin/users')
								? 'page'
								: null}
							class="arkive-tab min-w-fit p-1.5 {$page.url.pathname.includes('/admin/users')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin">{$i18n.t('Users')}</a
						>

						{#if $config?.features.enable_admin_analytics ?? true}
							<a
								draggable="false"
								aria-current={$page.url.pathname.includes('/admin/analytics') ? 'page' : null}
								class="arkive-tab min-w-fit p-1.5 {$page.url.pathname.includes('/admin/analytics')
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
								href="/admin/analytics">{$i18n.t('Analytics')}</a
							>
						{/if}

						<a
							draggable="false"
							aria-current={$page.url.pathname.includes('/admin/settings') ? 'page' : null}
							class="arkive-tab min-w-fit p-1.5 {$page.url.pathname.includes('/admin/settings')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/settings">{$i18n.t('Settings')}</a
						>
					</div>
				</div>
			</div>
		</nav>

		<div class="admin-content pb-1 flex-1 max-h-full overflow-y-auto">
			<slot />
		</div>
	</div>
{/if}

<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext } from 'svelte';
	import { user } from '$lib/stores';

	const i18n = getContext<Writable<i18nType>>('i18n');

	type Permission = {
		label: string;
		key: string;
		category: string;
	};

	const workspacePerms: Permission[] = [
		{ label: 'Create Models', key: 'workspace.models', category: 'workspace' },
		{ label: 'Create Knowledge Bases', key: 'workspace.knowledge', category: 'workspace' },
		{ label: 'Create Prompts', key: 'workspace.prompts', category: 'workspace' },
		{ label: 'Create Tools', key: 'workspace.tools', category: 'workspace' },
		{ label: 'Create Skills', key: 'workspace.skills', category: 'workspace' },
		{ label: 'Import Models', key: 'workspace.models_import', category: 'workspace' },
		{ label: 'Export Models', key: 'workspace.models_export', category: 'workspace' }
	];

	const sharingPerms: Permission[] = [
		{ label: 'Share Knowledge Bases', key: 'sharing.knowledge', category: 'sharing' },
		{ label: 'Make Knowledge Bases Public', key: 'sharing.public_knowledge', category: 'sharing' },
		{ label: 'Share Models', key: 'sharing.models', category: 'sharing' },
		{ label: 'Make Models Public', key: 'sharing.public_models', category: 'sharing' },
		{ label: 'Share Prompts', key: 'sharing.prompts', category: 'sharing' },
		{ label: 'Share Tools', key: 'sharing.tools', category: 'sharing' }
	];

	const chatPerms: Permission[] = [
		{ label: 'Upload Files', key: 'chat.file_upload', category: 'chat' },
		{ label: 'Web Upload', key: 'chat.web_upload', category: 'chat' },
		{ label: 'Delete Chats', key: 'chat.delete', category: 'chat' },
		{ label: 'Edit Messages', key: 'chat.edit', category: 'chat' },
		{ label: 'Share Chats', key: 'chat.share', category: 'chat' },
		{ label: 'Export Chats', key: 'chat.export', category: 'chat' },
		{ label: 'Chat Controls', key: 'chat.controls', category: 'chat' },
		{ label: 'System Prompt Override', key: 'chat.system_prompt', category: 'chat' },
		{ label: 'Use Multiple Models', key: 'chat.multiple_models', category: 'chat' },
		{ label: 'Speech to Text', key: 'chat.stt', category: 'chat' },
		{ label: 'Text to Speech', key: 'chat.tts', category: 'chat' }
	];

	const featurePerms: Permission[] = [
		{ label: 'Web Search', key: 'features.web_search', category: 'features' },
		{ label: 'Image Generation', key: 'features.image_generation', category: 'features' },
		{ label: 'Code Interpreter', key: 'features.code_interpreter', category: 'features' },
		{ label: 'API Keys', key: 'features.api_keys', category: 'features' },
		{ label: 'Direct Tool Servers', key: 'features.direct_tool_servers', category: 'features' }
	];

	const getPermValue = (key: string): boolean => {
		if ($user?.role === 'admin') return true;
		const parts = key.split('.');
		const perms = ($user as any)?.permissions ?? {};
		let val: any = perms;
		for (const part of parts) {
			if (val == null || typeof val !== 'object') return false;
			val = val[part];
		}
		return val === true;
	};

	type Section = { title: string; perms: Permission[] };

	const sections: Section[] = [
		{ title: 'Workspace', perms: workspacePerms },
		{ title: 'Sharing', perms: sharingPerms },
		{ title: 'Chat', perms: chatPerms },
		{ title: 'Features', perms: featurePerms }
	];
</script>

<div id="tab-permissions" class="flex flex-col h-full justify-between text-sm">
	<div class="flex flex-col gap-6 overflow-y-scroll max-h-[28rem] md:max-h-full pr-1.5 pb-4">
		{#if $user?.role === 'admin'}
			<div
				class="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-green-500/10 border border-green-500/20 text-green-600 dark:text-green-400"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="size-4 shrink-0"
				>
					<path
						fill-rule="evenodd"
						d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z"
						clip-rule="evenodd"
					/>
				</svg>
				<div class="text-xs font-medium">
					{$i18n.t('You are an admin — you have full access to everything.')}
				</div>
			</div>
		{:else}
			<div class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
				{$i18n.t(
					'These are your current permissions. Contact an admin if you need access to something.'
				)}
			</div>
		{/if}

		{#each sections as section}
			<div>
				<div
					class="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-2"
				>
					{$i18n.t(section.title)}
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden divide-y divide-gray-100 dark:divide-gray-850"
				>
					{#each section.perms as perm}
						{@const allowed = getPermValue(perm.key)}
						<div class="flex items-center justify-between px-3.5 py-2.5">
							<span class="text-xs text-gray-700 dark:text-gray-300">{$i18n.t(perm.label)}</span>
							<div class="flex items-center gap-1.5 shrink-0">
								{#if allowed}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="size-4 text-green-500"
									>
										<path
											fill-rule="evenodd"
											d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
											clip-rule="evenodd"
										/>
									</svg>
									<span class="text-xs font-medium text-green-600 dark:text-green-400"
										>{$i18n.t('Allowed')}</span
									>
								{:else}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="size-4 text-gray-300 dark:text-gray-600"
									>
										<path
											fill-rule="evenodd"
											d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
											clip-rule="evenodd"
										/>
									</svg>
									<span class="text-xs font-medium text-gray-400 dark:text-gray-500"
										>{$i18n.t('Not allowed')}</span
									>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/each}
	</div>
</div>

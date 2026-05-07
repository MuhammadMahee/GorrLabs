<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { ARKIVE_NAME } from '$lib/stores';
	import { getContext } from 'svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');
</script>

<div id="tab-about" class="flex flex-col h-full justify-between space-y-3 text-sm mb-6">
	<div class="space-y-5 overflow-y-scroll max-h-[28rem] md:max-h-full">
		<div class="space-y-2">
			<div class="arkive-prism-text text-xl font-semibold">{$ARKIVE_NAME}</div>
			<p class="max-w-2xl text-sm leading-6 text-gray-600 dark:text-gray-300">
				{$ARKIVE_NAME} is an AI workspace for capturing knowledge, organizing conversations, and working
				with models, prompts, tools, and files in one controlled environment.
			</p>
		</div>

		<div class="grid gap-2 md:grid-cols-3">
			<div class="arkive-about-card">
				<div class="text-xs font-semibold text-gray-800 dark:text-gray-100">
					{$i18n.t('Knowledge')}
				</div>
				<div class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
					{$i18n.t('Keep important context searchable and ready for chat.')}
				</div>
			</div>

			<div class="arkive-about-card">
				<div class="text-xs font-semibold text-gray-800 dark:text-gray-100">
					{$i18n.t('Control')}
				</div>
				<div class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
					{$i18n.t('Manage access, settings, and workflows without losing oversight.')}
				</div>
			</div>

			<div class="arkive-about-card">
				<div class="text-xs font-semibold text-gray-800 dark:text-gray-100">
					{$i18n.t('Creation')}
				</div>
				<div class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
					{$i18n.t('Build with prompts, skills, tools, and model configurations.')}
				</div>
			</div>
		</div>
	</div>
</div>

<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import type { SessionUser } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import { createEventDispatcher } from 'svelte';
	import { getContext } from 'svelte';

	import { goto } from '$app/navigation';

	import { updateUserById, getUserGroupsById, getUserPolicyById, updateUserPolicyById } from '$lib/apis/users';

	import Modal from '$lib/components/common/Modal.svelte';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	import XMark from '$lib/components/icons/XMark.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import UserProfileImage from '$lib/components/chat/Settings/Account/UserProfileImage.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher();
	dayjs.extend(localizedFormat);

	type OAuthProvider = {
		sub?: string;
		[key: string]: unknown;
	};

	type EditableUser = {
		id?: string;
		profile_image_url: string;
		role: string;
		name: string;
		email: string;
		password: string;
		oauth?: Record<string, OAuthProvider>;
		created_at?: number;
	};

	export let show = false;
	export let selectedUser: EditableUser | null = null;
	export let sessionUser: SessionUser;

	$: if (show) {
		init();
	}

	const init = () => {
		if (selectedUser) {
			_user = {
				id: selectedUser.id,
				profile_image_url: selectedUser.profile_image_url ?? '',
				role: selectedUser.role ?? 'pending',
				name: selectedUser.name ?? '',
				email: selectedUser.email ?? '',
				password: '',
				oauth: selectedUser.oauth,
				created_at: selectedUser.created_at
			};
			loadUserGroups();
			loadUserPolicy();
		}
	};

	let _user: EditableUser = {
		profile_image_url: '',
		role: 'pending',
		name: '',
		email: '',
		password: ''
	};

	let userGroups: Array<{ id: string; name: string }> | null = null;

	type UserPolicy = {
		clearance_level: number;
		department: string;
		region: string;
		can_export: boolean;
		can_upload: boolean;
	};

	let _policy: UserPolicy = {
		clearance_level: 0,
		department: '',
		region: '',
		can_export: false,
		can_upload: true
	};

	const clearanceLevels = [
		{ value: 0, label: 'Public' },
		{ value: 1, label: 'Internal' },
		{ value: 2, label: 'Confidential' },
		{ value: 3, label: 'Restricted' }
	];

	const submitHandler = async () => {
		if (!selectedUser?.id) return;

		const res = await updateUserById(localStorage.token, selectedUser.id, _user).catch((error) => {
			toast.error(`${error}`);
		});

		await updateUserPolicyById(localStorage.token, selectedUser.id, {
			clearance_level: _policy.clearance_level,
			department: _policy.department || null,
			region: _policy.region || null,
			can_export: _policy.can_export,
			can_upload: _policy.can_upload,
			allowed_collection_ids: []
		}).catch(() => {});

		if (res) {
			dispatch('save');
			show = false;
		}
	};

	const loadUserGroups = async () => {
		if (!selectedUser?.id) return;
		userGroups = null;

		userGroups = await getUserGroupsById(localStorage.token, selectedUser.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
	};

	const loadUserPolicy = async () => {
		if (!selectedUser?.id) return;

		const policy = await getUserPolicyById(localStorage.token, selectedUser.id).catch(() => null);
		if (policy) {
			_policy = {
				clearance_level: policy.clearance_level ?? 0,
				department: policy.department ?? '',
				region: policy.region ?? '',
				can_export: policy.can_export ?? false,
				can_upload: policy.can_upload ?? true
			};
		} else {
			_policy = { clearance_level: 0, department: '', region: '', can_export: false, can_upload: true };
		}
	};
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class=" text-lg font-medium self-center">{$i18n.t('Edit User')}</div>
			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				on:click={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<form
					class="flex flex-col w-full"
					on:submit|preventDefault={() => {
						submitHandler();
					}}
				>
					<div class=" px-5 pt-3 pb-5 w-full">
						<div class="flex self-center w-full">
							<div class=" self-start h-full mr-6">
								<UserProfileImage
									imageClassName="size-14"
									bind:profileImageUrl={_user.profile_image_url}
									user={_user}
								/>
							</div>

							<div class=" flex-1">
								<div class="overflow-hidden w-ful mb-2">
									<div class=" self-center capitalize font-medium truncate">
										{selectedUser.name}
									</div>

									<div class="text-xs text-gray-500">
										{$i18n.t('Created at')}
										{dayjs(selectedUser.created_at * 1000).format('LL')}
									</div>
								</div>

								<div class=" flex flex-col space-y-1.5">
									{#if (userGroups ?? []).length > 0}
										<div class="flex flex-col w-full text-sm">
											<div class="mb-1 text-xs text-gray-500">{$i18n.t('User Groups')}</div>

											<div class="flex flex-wrap gap-1 my-0.5 -mx-1">
												{#each userGroups as userGroup}
													<span
														class="px-1.5 py-0.5 rounded-xl bg-gray-100 dark:bg-gray-850 text-xs"
													>
														<a
															href={'/admin/users/groups?id=' + userGroup.id}
															on:click|preventDefault={() =>
																goto('/admin/users/groups?id=' + userGroup.id)}
														>
															{userGroup.name}
														</a>
													</span>
												{/each}
											</div>
										</div>
									{/if}

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Role')}</div>

										<div class="flex-1">
											<select
												class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
												bind:value={_user.role}
												aria-label={$i18n.t('Role')}
												disabled={_user.id == sessionUser.id}
												required
											>
												<option value="admin">{$i18n.t('Admin')}</option>
												<option value="user">{$i18n.t('User')}</option>
												<option value="pending">{$i18n.t('Pending')}</option>
											</select>
										</div>
									</div>

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Name')}</div>

										<div class="flex-1">
											<input
												class="w-full text-sm bg-transparent outline-hidden"
												type="text"
												bind:value={_user.name}
												aria-label={$i18n.t('Name')}
												placeholder={$i18n.t('Enter Your Name')}
												autocomplete="off"
												required
											/>
										</div>
									</div>

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Email')}</div>

										<div class="flex-1">
											<input
												class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
												type="email"
												bind:value={_user.email}
												aria-label={$i18n.t('Email')}
												placeholder={$i18n.t('Enter Your Email')}
												autocomplete="off"
												required
											/>
										</div>
									</div>

									{#if _user?.oauth}
										<div class="flex flex-col w-full">
											<div class=" mb-1 text-xs text-gray-500">{$i18n.t('OAuth ID')}</div>

											<div class="flex-1 text-sm break-all mb-1 flex flex-col space-y-1">
												{#each Object.keys(_user.oauth) as key}
													<div>
														<span class="text-gray-500">{key}</span>
														<span class="">{_user.oauth[key]?.sub}</span>
													</div>
												{/each}
											</div>
										</div>
									{/if}

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('New Password')}</div>

										<div class="flex-1">
											<SensitiveInput
												outerClassName="flex flex-1 bg-transparent"
												inputClassName="w-full text-sm bg-transparent outline-hidden"
												type="password"
												placeholder={$i18n.t('Enter New Password')}
												bind:value={_user.password}
												autocomplete="new-password"
												required={false}
											/>
										</div>
									</div>
								</div>
							</div>
						</div>

						<div class="mt-4 pt-3 border-t border-gray-100 dark:border-gray-800">
							<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Access Policy</div>

							<div class="flex flex-col space-y-1.5">
								<div class="flex flex-col w-full">
									<div class="mb-1 text-xs text-gray-500">{$i18n.t('Clearance Level')}</div>
									<select
										class="w-full text-sm bg-transparent outline-hidden"
										bind:value={_policy.clearance_level}
										aria-label={$i18n.t('Clearance Level')}
									>
										{#each clearanceLevels as level}
											<option value={level.value}>{level.label}</option>
										{/each}
									</select>
								</div>

								<div class="flex flex-col w-full">
									<div class="mb-1 text-xs text-gray-500">{$i18n.t('Department')}</div>
									<input
										class="w-full text-sm bg-transparent outline-hidden"
										type="text"
										bind:value={_policy.department}
										placeholder={$i18n.t('e.g. HR, Finance, Engineering')}
										autocomplete="off"
									/>
								</div>

								<div class="flex flex-col w-full">
									<div class="mb-1 text-xs text-gray-500">{$i18n.t('Region')}</div>
									<input
										class="w-full text-sm bg-transparent outline-hidden"
										type="text"
										bind:value={_policy.region}
										placeholder={$i18n.t('e.g. EU, US, APAC')}
										autocomplete="off"
									/>
								</div>

								<div class="flex items-center justify-between w-full">
									<div class="text-xs text-gray-500">{$i18n.t('Can Export')}</div>
									<input type="checkbox" bind:checked={_policy.can_export} />
								</div>

								<div class="flex items-center justify-between w-full">
									<div class="text-xs text-gray-500">{$i18n.t('Can Upload')}</div>
									<input type="checkbox" bind:checked={_policy.can_upload} />
								</div>
							</div>
						</div>

						<div class="flex justify-end pt-3 text-sm font-medium">
							<button
								class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full flex flex-row space-x-1 items-center"
								type="submit"
							>
								{$i18n.t('Save')}
							</button>
						</div>
					</div>
				</form>
			</div>
		</div>
	</div>
</Modal>

<style>
	input::-webkit-outer-spin-button,
	input::-webkit-inner-spin-button {
		/* display: none; <- Crashes Chrome on hover */
		-webkit-appearance: none;
		margin: 0; /* <-- Apparently some margin are still there even though it's hidden */
	}



</style>

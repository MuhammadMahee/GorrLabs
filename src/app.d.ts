// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces

declare global {
	// Vite define globals
	const APP_VERSION: string;
	const APP_BUILD_HASH: string;

	interface Navigator {
		msMaxTouchPoints?: number;
	}

	interface MediaTrackConstraintSet {
		cursor?: ConstrainDOMString;
	}

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}
}

export {};

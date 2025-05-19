---
title: Introducing domain-driven design to a frontend application
date: 2023-05-07T19:29:57-03:00
lastmod: 2023-07-23T19:38:30-03:00
author: Willian Nascimento

description: Introducing domain-driven design to a frontend application
categories: [Programming]
tags: [English]

draft: false
---

After diving into our React.js project at work, experiencing the mysterious ways in which it was built and grappling with the unintended consequences of poor decisions, we decided it was time to shake things up a bit.

Changes were necessary, and the first major one we implemented was transitioning from Javascript to Typescript. Typescript is a strongly and statically typed language, it allows developers to define types for variables, functions and objects, which helps catch type-related errors during development. It also has neat features like discriminated unions; with them, it's possible to represent a value that can take on different types.

```ts
// For representing entity validity
type Entity =
	| UnverifiedEntity
	| ValidEntity

// For representing state machines
type State =
	| Uninitialized
	| Processing
	| Finished
	| WithError
```
*But anyways, lets go back to the main topic..*

Our goal was to make the transition gradual, easy to understand, and capable of releasing small, well-contained migrations in production. Moving to Typescript was a game-changer and led the team towards safer and better-structured code. It became the driving theme for other improvements, including the adoption of domain-driven design.

I plan to write on domain-centric solutions alone, so I'm not going in depth about it here, but in summary, it centralizes the development around it, using cool ideas such as bringing domain experts and developers close together using a common language, plus other stuff like bounded contexts.

At the time we didn't realize how impactful this would be, and the challenges that came with it.

Initially we split the project into different layers, this was important for separation of concerns. We had the Domain for views, models, dtos and mappers. The Infrastructure handled repositories, helpers and utils. The Application had basically the React screens and hooks.

However, instead of creating a Service layer, which is common in this type of layered architecture, we divided the screens into different files. The primary ones were Screen.tsx for HTML components, and ScreenService.tsx, a kind of hook/context provider that acted much like a service, orchestrating the flow. This gave us some flexibility and made maintenance easier.

> It's worth noting that the general design applied here is a mix of different patterns and, as such, does not concern itself with architectural purity or anything of the sort. DDD ultimately means the application is Domain-centric.

```md
# inside ./src
├── domain
	├── models
	├── dtos
	├── views
	└── mappers
├── infrastructure
	├── api
	└── utils
└── application
	└──  order
		├── components
		├── Order.tsx
		└── OrderService.tsx
```

Second, we had to figure out how to write code that would allow for a smooth interaction between types from different layers. It's a bit different when you apply these concepts to the frontend, and some adjustments had to be made.

In essence, view types are flexible and used to hold user inputs; validation logic can usually be found close to them. Dto types are similar to view types, and serve as the contract between the application and external sources when fetching or sending data.

For these two layers to have a healthy interaction with the domain (in our case, at least), it was necessary to provide functionality to enable flows that need not the domain, to work seemlessly. Meaning, the creation of a new resource that has been validated already in the view layer, to be sent to the backend without friction.

...In any case, we arrived at something similar to this:

```ts
// Unique symbol used to make the construction of valid types impossible
// without using the proper `validate` function.
const modalitySymbol = Symbol("Modality");

type Modality = {
	[modalitySymbol]: true // the value here doesn't matter
	name: string
	id: string
}

function createModality(modality: ModalityDto): Modality {
	if (modality.id === undefined || modality.id.trim().length === 0)
		throw new ValidationError({message: ErrorMessages.cannotBeNullOrEmpty("id")})

	return {
		[modalitySymbol]: true,
		id: modality.id,
		name: modality.name,
	}
}

// Exporting types and funcs at the end of the file
// instead of using `export` in their definition is good for readability,
// but also to avoid circular dependencies between modules.
export type { Modality }
export { createModality }
```

```ts
type ModalityDto = {
	id?: string;
	name: string;
};

export type { ModalityDto };
```

The mappers were written separately. We implemented mostly functions that mapped between domain and dto types. Some were also created to map from a view type to a dto (related to the necessity to avoid friction I mentioned earlier).

And mind you, this solution was practical, it allowed us to move forward with the changes, but there's still some polishing to do. I would like to achieve an organization similar to F# modules, something like this:

```ts
namespace Modality {
	export namespace Domain {
		// Unique symbol used to make the construction of valid types impossible
		// without using the proper `validate` function.
		const modalitySymbol = Symbol("Modality");
		
		export type Modality = {
			[modalitySymbol]: true // the value here doesn't matter
			name: string
			id: string
		}
	
		export function create(modality: Dto.Modality): Modality {
			if (modality.id === undefined || modality.id.trim().length === 0)
				throw new ValidationError({message: ErrorMessages.cannotBeNullOrEmpty("id")})
	
			return {
				[modalitySymbol]: true,
				id: modality.id,
				name: modality.name,
			}
		}
	}

	export namespace View {
		export type Modality = {
			name?: string
			id?: string
		}

		export function toModel(modality: Modality) {}

		export function ofModel(modality: Domain.Modality) {}
	}

	export namespace Dto {
		export type Modality = {
			name: string
			id?: string
		}

		export function toModel(modality: Modality) {}

		export function ofModel(modality: Domain.Modality) {}
	}
}

export default Modality
```

Having finished modeling the domain and other value object types, we were ready to design the repositories. For this purpose, we used OOP (*object oriented programming*) to define a base class responsible for implementing the essential code for communicating with the backend.

```ts
export default abstract class BaseApi {
	constructor(apiAddress: string) {
		this.baseUrl = GetDomain() + apiAddress;
	}

	private readonly baseUrl: string;

	protected isResponseSuccessful(statusCode: number) {
		if ([200, 201, 202, 204, 206].includes(statusCode))
			return true;

		return false;
	}

	protected async request<T>(
		uri: string,
		method: HttpMethod,
		body: object | null = null
	): Promise<AxiosResponse<T>> {
		let req: AxiosRequestConfig = {
			baseURL: this.baseUrl,
			url: uri,
			method: method,
			headers: {}, // auth here if any
			data: body === null ? null : JSON.stringify(body),
		};

		let resp: AxiosResponse<T>;
		try {
			resp = await Axios.request<T>(req);
		} catch (err: unknown) {
			let axiosError = err as AxiosError<T>;
			if (
				axiosError?.isAxiosError &&
				axiosError?.response !== null &&
				axiosError?.response !== undefined
			) {
				resp = axiosError.response;
				return resp;
			}

			// Rethrow error up the stack, we don't want to catch here
			// because there are no errors expected besides AxiosError.
			throw err;
		}

		return resp;
	}
}
```

Then, we inherited the BaseApi for any of our APIs.

```ts
interface ISomeApi {
    getSomethingById: (id: string) => Promise<SomethingDto>;
}

class SomeApi extends BaseApi implements ISomeApi {
    async getSomethingById(id: string): Promise<SomethingDto> {
        let resp = await this.request<SomethingDto>(`something/${id}`, HttpMethod.Get);
        
        if (!this.isResponseSuccessful(resp.status))
            throw new Error("Could not get something by id.");

        return resp.data;
    }
}

export const someApi: ISomeApi = new SomeApi("api/");
```

I'm still debating on whether we should have written the repositories in the same namespaces as the domain entities, creating nice bounded contexts, or if the application would struggle to handle such tight structures. 

Anyhow, that can change in the future.

With the Infrastructure layer now in place, we could finally wrap it all up in the services. These services would be responsible for orchestrating the flow of data and business logic between the user interface and the repositories.

Here's an example of service, which in our case is just a React hook:

```ts
export default function someService() {
	const [something, setSomething] = useState<SomethingView>({});
	
	useEffect(() => {
		getSomething(sellerId);
	}, []);

	const getSomething = async (id: string): Promise<void> => {
		setIsLoading(true);

		try {
			let data: SomethingDto = await someApi.getSomethingById(id);
			let domainObj = createModality(data);
			// Do some business logic here using domainObj..
			let viewObj = ModalityMapper.toView(domainObj);
			setModalities(viewObj);
		} catch {
			ToastComponent({
				status: "error",
				title: "Some error :(",
				message: "Something could not be loaded",
			});
		}

		setTimeout(() => {
			setIsLoading(false);
		}, 500);
	};

	return {
		// Props
		something,
		isLoading,
		// Functions
		getSomething,
	};
}
```

At this point I've summarized pretty much all the relevant events, and omitted many of others, like our attempts to use external packages to validate forms, which we didn't enjoy very much, and the migration from bootstrap to MUI; but those are reserved for another day..

For now, that's what I have to share about introducing domain-driven design to a frontend application.

---

As for the results that blossomed from this adventure, I can't share much in details, but there's one that is special to me. The amount of bugs that were escalated for fix, which were noticeable previously to these changes, have now resumed in, believe it or not, zero (statistics from the three months after first release in production).

In conclusion, transitioning from Javascript to Typescript, as well as writing code driven by the domain, have provided just enough strictness to create a safer, faster, and more enjoyable development cycle for the frontend team. It was an extremely enriching and rewarding experience, and I recommend other teams to dare explore!

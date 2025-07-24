interface FunctionDefinition {
    name: string
    description: string
    parameters?: {
        type: string
        properties?: {
            [key: string]: {
                type: string
                description: string
            }
        }
        required?: string[]
    }
}

const similarTo: FunctionDefinition = {
  name: 'similar_to',
  description:
    'Get similar node names to the given node name and an optional origin file path.',
  parameters: {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        description:
          'The name of the node to find similar nodes for. The name is case sensitive. In the case of methods, the name should include the parent class name as class_name.method_name.',
      },
    },
    required: ['name'],
  },
}

const getCode: FunctionDefinition = {
  name: 'get_code',
  description:
    'Get the code of a node by its name and an optional origin file path. The origin file path is useful when there are 2 nodes or more with the same name.',
  parameters: {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        description:
          'The name of the node to get the code for. The name is case sensitive. In the case of methods, the name should include the parent class name as class_name.method_name. In the case of files, the name should be the file name, for example, "file_name.py"',
      },
      path: {
        type: 'string',
        description:
          'The origin file path of the node. This is useful when there are 2 nodes or more with the same name. For example, "src/file_name.py"',
      },
    },
    required: ['name'],
  },
}

const findDirectConnections: FunctionDefinition = {
  name: 'find_direct_connections',
  description:
    'Get the direct connections of a node by its name and an optional origin file path. The origin file path is useful when there are 2 nodes or more with the same name. \
This will return the directly connected nodes: parent nodes (those that reference this node) and child nodes (those this node references directly). It only considers first-level relationships, without traversing further dependencies.',
  parameters: {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        description:
          'The name of the node to get the direct connections for. The name is case sensitive. In the case of methods, the name should include the parent class name as class_name.method_name.',
      },
      path: {
        type: 'string',
        description:
          'The origin file path of the node. This is useful when there are 2 nodes or more with the same name.',
      },
    },
    required: ['name'],
  },
}

const nodesSemanticSearch: FunctionDefinition = {
  name: 'nodes_semantic_search',
  description:
    'Get a list of nodes (functions, classes, etc) which functionality is related to the given query by semantic similarity.',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'The user query to search for.',
      },
    },
    required: ['query'],
  },
}

const docsSemanticSearch: FunctionDefinition = {
  name: 'docs_semantic_search',
  description:
    'Get documentation related to the given query using semantic search. This run over documentation files only, such as markdown and reStructuredText.',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'The user query to search for.',
      },
    },
    required: ['query'],
  },
}

const getUsageDependencyLinks: FunctionDefinition = {
  name: 'get_usage_dependency_links',
  description:
    'Get an adjacency list of nodes influenced by a node given its name and an optional origin file path. The origin file path is useful when there are 2 nodes or more with the same name. \
This is useful to detect all nodes affected by changes in the code. Each node is represented by its origin file path and its name in the format origin_file_path::node_name.',
  parameters: {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        description:
          'The name of the node to get the adjacency list for. The name is case sensitive. In the case of methods, the name should include the parent class name as class_name.method_name.',
      },
      path: {
        type: 'string',
        description:
          'The origin file path of the node. This is useful when there are 2 nodes or more with the same name.',
      },
    },
    required: ['name'],
  },
}

const getFolderTreeStructure: FunctionDefinition = {
  name: 'get_folder_tree_structure',
  description:
    'Returns the folder tree structure of the given folder path. Useful to understand what files and subfolders are inside the given folder.',
  parameters: {
    type: 'object',
    properties: {
      path: {
        type: 'string',
        description: 'The path to the folder to get the tree structure for.',
      },
    },
    required: ['path'],
  },
}

export const graphToolsDescriptions = [
  docsSemanticSearch,
  findDirectConnections,
  getCode,
  getUsageDependencyLinks,
  getFolderTreeStructure,
  nodesSemanticSearch,
  similarTo,
]

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import docker
import traceback

# Configurações
subscription_id = '22c9789f-d4e7-4802-a160-8b39e1bb2a17'  # Substitua pelo seu ID de assinatura
resource_group = 'myResourceGroup'  # Nome do grupo de recursos
acr_name = 'automacaosite'  # Nome do Azure Container Registry
dockerhub_image = 'anderson0920/flask-library-app:latest'  # Imagem no Docker Hub
image_name = 'my-existing-image'  # Nome da imagem no ACR
tag = 'latest'  # Tag da imagem Docker
container_instance_name = 'siteapiteste'  # Nome da instância de container
location = 'eastus'  # Localização do recurso

# Autenticação usando DefaultAzureCredential
credential = DefaultAzureCredential()

# Criar o Grupo de Recursos
print("Criando o grupo de recursos...")
resource_client = ResourceManagementClient(credential, subscription_id)
resource_client.resource_groups.create_or_update(resource_group, {'location': location})
print("Grupo de recursos criado com sucesso.")

# Criar o Azure Container Registry (ACR)
print("Criando o Azure Container Registry...")
acr_client = ContainerRegistryManagementClient(credential, subscription_id)
acr_client.registries.begin_create(resource_group, acr_name, {
    'location': location,
    'sku': {'name': 'Basic'},
    'admin_user_enabled': True  # Habilita o usuário admin no ACR
}).result()
print("Azure Container Registry criado com sucesso.")

# Obter o Login Server e Credenciais do ACR
acr_registry = acr_client.registries.get(resource_group, acr_name)
acr_login_server = acr_registry.login_server
acr_credentials = acr_client.registries.list_credentials(resource_group, acr_name)
acr_username = acr_credentials.username
acr_password = acr_credentials.passwords[0].value

# Login no Docker usando o ACR
docker_client = docker.from_env()
docker_client.login(username=acr_username, password=acr_password, registry=acr_login_server)
print(f"Login no ACR ({acr_login_server}) realizado com sucesso.")

# Baixar a imagem do Docker Hub
try:
    print(f"Fazendo pull da imagem {dockerhub_image} do Docker Hub...")
    image = docker_client.images.pull(dockerhub_image)
    print(f"Imagem {dockerhub_image} baixada com sucesso.")
except docker.errors.ImageNotFound:
    print(f"Erro: Imagem {dockerhub_image} não encontrada no Docker Hub.")
    exit(1)

# Adicionar tag para o ACR
try:
    print(f"Adicionando tag para a imagem no ACR...")
    image.tag(f'{acr_login_server}/{image_name}', tag=tag)
    print(f"Imagem marcada como {acr_login_server}/{image_name}:{tag}.")
except Exception as e:
    print(f"Erro ao adicionar tag: {e}")
    exit(1)

# Enviar a imagem para o ACR
try:
    print(f"Fazendo push da imagem para o ACR...")
    docker_client.images.push(f'{acr_login_server}/{image_name}', tag=tag)
    print(f"Imagem enviada para o ACR: {acr_login_server}/{image_name}:{tag}.")
except Exception as e:
    print(f"Erro ao enviar imagem para o ACR: {e}")
    exit(1)

# Criar o Azure Container Instance (ACI)
aci_client = ContainerInstanceManagementClient(credential, subscription_id)

container_resource = {
    "location": location,
    "properties": {
        "containers": [
            {
                "name": container_instance_name,
                "properties": {
                    "image": f'{acr_login_server}/{image_name}:{tag}',
                    "resources": {
                        "requests": {
                            "cpu": 1.0,
                            "memoryInGB": 1.5
                        }
                    },
                    "ports": [
                        {
                            "protocol": "TCP",
                            "port": 80
                        }
                    ]
                }
            }
        ],
        "osType": "Linux",
        "ipAddress": {
            "type": "Public",
            "dnsNameLabel": "siteapitestev1",  # Substitua por um valor único
            "ports": [
                {
                    "protocol": "TCP",
                    "port": 80
                }
            ]
        },
        # Credenciais do ACR para autenticar o ACI
        "imageRegistryCredentials": [
            {
                "server": acr_login_server,
                "username": acr_username,
                "password": acr_password
            }
        ]
    }
}

try:
    print("Criando o Azure Container Instance...")
    aci_client.container_groups.begin_create_or_update(resource_group, container_instance_name, container_resource).result()
    print("Container Instance criado com sucesso!")
except Exception as e:
    print(f"Erro ao criar o Container Instance: {e}")
    traceback.print_exc()
    exit(1)

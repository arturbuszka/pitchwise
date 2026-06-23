# .NET API (ASP.NET Core). Build context: api-dotnet/
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY *.csproj ./
RUN dotnet restore
COPY . ./
RUN dotnet publish -c Release -o /out

FROM mcr.microsoft.com/dotnet/aspnet:9.0
WORKDIR /app
COPY --from=build /out ./
ENV ASPNETCORE_URLS=http://0.0.0.0:8000
EXPOSE 8000
ENTRYPOINT ["dotnet", "PitchWise.Api.dll"]
